"""Authoritative provider choice and immutable per-operation GPT provenance."""
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
import re
import threading


FEATURES = {'F1': 'Movie recommendations', 'F2': 'AI Control', 'F3': 'Movie Smart Match',
            'F4': 'IPTV classification', 'F5': 'IPTV candidate matching', 'F6': 'YouTube movie search'}
CONFIG_KEYS = ('ai_provider', 'chatgpt', 'ai_config_generation')


class AIProviderError(ValueError):
    def __init__(self, code, status=400):
        self.code, self.status = code, status
        super().__init__(code)


def canonical_count(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise AIProviderError('invalid_positive_whole_number')
    text = str(value).strip()
    if not re.fullmatch(r'[0-9]+', text):
        raise AIProviderError('invalid_positive_whole_number')
    result = text.lstrip('0')
    if not result:
        raise AIProviderError('invalid_positive_whole_number')
    return result


def normalized_config(raw):
    gpt = raw.get('chatgpt') or {}
    return {'provider': raw.get('ai_provider', 'ollama'),
            'generation': raw.get('ai_config_generation', 0),
            'chatgpt': {'active_account_id': gpt.get('active_account_id'), 'model': gpt.get('model', ''),
                        'recommendation_count': canonical_count(gpt.get('recommendation_count', '15')),
                        'allow_movie_identity_hints': gpt.get('allow_movie_identity_hints', False),
                        'allow_iptv_titles': gpt.get('allow_iptv_titles', False)}}


@dataclass(frozen=True)
class AISelection:
    provider: str
    config_generation: int
    account_id: str | None
    model: str
    skill_id: str
    skill_version: str
    skill_hash: str
    feature: str
    domain_id: str | None = None

    def public(self):
        return asdict(self)


class AIProviderService:
    def __init__(self, load_config, save_config, *, accounts=lambda: [], skill_loader=None,
                 dependencies=lambda feature, domain: None,
                 legacy_readiness=lambda feature, domain: {'ready': False, 'reason': 'legacy_feature_owner'}):
        self.load_config, self.save_config = load_config, save_config
        self.accounts, self.skill_loader, self.dependencies = accounts, skill_loader, dependencies
        self.legacy_readiness = legacy_readiness
        self._lock = threading.RLock()

    def _config(self):
        return normalized_config(self.load_config())

    def public_config(self):
        with self._lock:
            config = self._config()
            # Legacy/default installs never touch the new credential or skill owner.
            profiles = self.accounts() if config['provider'] == 'chatgpt' else []
            safe = [{key: p.get(key) for key in ('account_id', 'email', 'label', 'connected', 'plan_enabled')}
                    for p in profiles]
            return {**config, 'accounts': safe, 'features': self.features()}

    def update_config(self, payload, expected_generation):
        allowed = {'provider', 'active_account_id', 'chatgpt_model', 'recommendation_count',
                   'allow_movie_identity_hints', 'allow_iptv_titles'}
        if not isinstance(payload, dict) or set(payload) - allowed:
            raise AIProviderError('unknown_config_field')
        with self._lock:
            current = self._config()
            if isinstance(expected_generation, bool) or not isinstance(expected_generation, int):
                raise AIProviderError('invalid_generation')
            if expected_generation != current['generation']:
                raise AIProviderError('stale_generation', 409)
            provider = payload.get('provider', current['provider'])
            if provider not in ('ollama', 'chatgpt'):
                raise AIProviderError('invalid_provider')
            gpt = deepcopy(current['chatgpt'])
            for key in ('allow_movie_identity_hints', 'allow_iptv_titles'):
                if key in payload:
                    if not isinstance(payload[key], bool):
                        raise AIProviderError('invalid_consent_value')
                    gpt[key] = payload[key]
            if 'recommendation_count' in payload:
                gpt['recommendation_count'] = canonical_count(payload['recommendation_count'])
            if 'chatgpt_model' in payload:
                if not isinstance(payload['chatgpt_model'], str):
                    raise AIProviderError('invalid_model')
                gpt['model'] = payload['chatgpt_model'].strip()
            if 'active_account_id' in payload:
                account = payload['active_account_id']
                if account is not None and not any(p['account_id'] == account for p in self.accounts()):
                    raise AIProviderError('unknown_account')
                gpt['active_account_id'] = account
            updated = deepcopy(self.load_config())
            updated.update(ai_provider=provider, chatgpt=gpt, ai_config_generation=current['generation'] + 1)
            self.save_config(updated)
            return self.public_config()

    def readiness(self, feature, domain_id=None):
        if feature not in FEATURES:
            raise AIProviderError('unknown_feature')
        config = self._config()
        if config['provider'] == 'ollama':
            return {**self.legacy_readiness(feature, domain_id), 'policy': 'legacy_feature_owner'}
        return self._gpt_readiness(config['chatgpt'], feature, domain_id)

    def _gpt_readiness(self, gpt, feature, domain_id):
        profile = next((p for p in self.accounts() if p['account_id'] == gpt['active_account_id']), None)
        reason = None
        if not profile or not profile.get('connected'):
            reason = 'account_disconnected'
        elif not profile.get('plan_enabled'):
            reason = 'consent_required'
        elif not gpt['model']:
            reason = 'model_required'
        elif (feature == 'F3' and not gpt['allow_movie_identity_hints']) or (feature in ('F4', 'F5') and not gpt['allow_iptv_titles']):
            reason = 'consent_required'
        else:
            reason = self.dependencies(feature, domain_id)
            if not reason:
                try:
                    if not self.skill_loader or not self.skill_loader(feature):
                        reason = 'skill_missing'
                except (OSError, ValueError, KeyError, ImportError):
                    reason = 'skill_missing'
        return {'ready': not bool(reason), 'reason': reason}

    def features(self, domain_id=None):
        return [{'id': feature, 'name': name, **self.readiness(feature, domain_id)}
                for feature, name in FEATURES.items()]

    def snapshot(self, feature, *, domain_id=None):
        with self._lock:
            config = self._config()
            if feature not in FEATURES:
                raise AIProviderError('unknown_feature')
            if config['provider'] == 'ollama':
                return AISelection('ollama', config['generation'], None,
                    self.load_config().get('ollama_model', ''), 'ollama:' + feature, 'legacy', '', feature, domain_id)
            ready = self.readiness(feature, domain_id)
            if not ready['ready']:
                raise AIProviderError(ready['reason'], 409)
            skill = self.skill_loader(feature)
            return AISelection('chatgpt', config['generation'], config['chatgpt']['active_account_id'],
                config['chatgpt']['model'], skill['id'], skill['version'], skill['hash'], feature, domain_id)

    def connection_selection(self, *, require_model=False):
        config = self._config()
        account = config['chatgpt']['active_account_id']
        if not account or not any(p['account_id'] == account and p.get('connected') for p in self.accounts()):
            raise AIProviderError('account_disconnected', 409)
        model = config['chatgpt']['model']
        if require_model and not model:
            raise AIProviderError('model_required', 409)
        return AISelection('chatgpt', config['generation'], account, model, 'connection', '1', '', 'connection')

    def for_feature(self, parent, feature, *, domain_id=None):
        if not isinstance(parent, AISelection) or parent.provider != 'chatgpt' or feature not in FEATURES:
            raise AIProviderError('invalid_parent_selection')
        with self._lock:
            current = self._config()['chatgpt']
            permission = self._gpt_readiness({**current, 'active_account_id': parent.account_id,
                                            'model': parent.model}, feature, domain_id)
            if not permission['ready']:
                raise AIProviderError(permission['reason'], 409)
            skill = self.skill_loader(feature)
            return replace(parent, feature=feature, domain_id=domain_id, skill_id=skill['id'],
                           skill_version=skill['version'], skill_hash=skill['hash'])

    def check_evidence_scopes(self, scopes):
        current = self._config()['chatgpt']
        permissions = {'iptv_titles': current['allow_iptv_titles'],
                       'movie_identity_hints': current['allow_movie_identity_hints']}
        if any(scope not in permissions or not permissions[scope] for scope in scopes):
            raise AIProviderError('saved_context_requires_evidence_permission; enable the relevant opt-in or start a new session', 409)
