"""Bounded desktop regression of the real player, authenticated IPC, offline fixtures.
Requires pywinauto on PYTHONPATH (test tooling only). Never connects to CP/catalog.
"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time
import uuid

DLL_DIRECTORIES = [os.add_dll_directory(str(Path(entry)/"pywin32_system32"))
                   for entry in sys.path if (Path(entry)/"pywin32_system32").is_dir()]

os.environ.setdefault('CP_TEST_MODE', '1')
os.environ.setdefault('CP_TEST_ROOT', str(Path(os.environ.get('TEMP', '.')) / ('cp-menu-ui-' + uuid.uuid4().hex)))

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from smoke_player import (message, find_visible_window, show_test_window, capture_window,
                          click_window_fraction, send_window_key, move_window_fraction)
from services.player_config import default_player_config
from services.player_manager import safe_player_preferences
from services.player_protocol import validate_message
from services.player_windows_pipe import WindowsNamedPipeServer


def wait_for(predicate, description, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value: return value
        time.sleep(.05)
    raise AssertionError('Timed out: ' + description)


class Session:
    def __init__(self, runtime, fixtures, output, scale):
        from pywinauto import Desktop
        self.output = output
        self.sid = uuid.uuid4().hex
        token = secrets.token_urlsafe(32)
        self.tr = WindowsNamedPipeServer('cp-menu-' + self.sid)
        self.events = []
        self.sequence = 0
        self.generation = 0
        self.stop = threading.Event()
        self.closing = False
        self.fixtures = fixtures
        env = {k: v for k, v in os.environ.items() if k.upper() in {'SYSTEMROOT','WINDIR','TEMP','TMP','PATH'}}
        isolated = fixtures / self.sid
        env.update(QT_FORCE_STDERR_LOGGING='1',CP_PLAYER_PIPE='cp-menu-' + self.sid, CP_PLAYER_SESSION_ID=self.sid,
                   CP_PLAYER_SESSION_TOKEN=token, CP_PLAYER_PROTOCOL='1',
                   CP_PLAYER_CACHE_ROOT=str(isolated/'cache'), APPDATA=str(isolated/'roaming'),
                   LOCALAPPDATA=str(isolated/'local'), QT_SCALE_FACTOR=str(scale / (ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100)))
        for name in ['cache', 'roaming', 'local']: (isolated/name).mkdir(parents=True)
        self.log = (output/'native-stderr.log').open('w',encoding='utf-8')
        self.p = subprocess.Popen([str(runtime/'cp-player.exe')], cwd=runtime,env=env,
                                  stdin=subprocess.DEVNULL,stdout=self.log,stderr=self.log)
        try: self.tr.accept(10)
        except Exception:
            code = self.p.poll()
            if code is None: self.p.terminate(); self.p.wait(5)
            self.tr.close(); self.log.close()
            raise AssertionError(f"Player startup failed; exit={code}; inspect native-stderr.log")
        hello = self.tr.receive(10)
        validate_message(hello,expected_type='hello',session_id=self.sid,token=token)
        self.events.append(hello)
        self.reader = threading.Thread(target=self._read,daemon=True)
        self.reader.start()
        self.desktop = Desktop(backend='uia')
        self.hwnd = wait_for(lambda: find_visible_window(self.p.pid),'native window')
        self.win = self.desktop.window(handle=self.hwnd).wrapper_object()
        show_test_window(self.hwnd)

    def _read(self):
        while not self.stop.is_set():
            try:
                event = self.tr.receive(.2)
                validate_message(event,session_id=self.sid)
                self.events.append(event)
            except TimeoutError: continue
            except Exception:
                if not self.closing and not self.stop.is_set() and self.p.poll() is None: self.events.append({'type':'reader.error'})
                break

    def send(self, kind, **payload):
        self.sequence += 1
        self.tr.send(message(self.sid,self.sequence,kind,**payload))

    def load(self, rows, current=0, media_type='movie', error='', resume=0, autoplay=False, media_file='menu.mkv'):
        self.generation += 1
        before = len(self.events)
        self.send('load',media_generation=self.generation,
                  media={'path':str((self.fixtures/media_file).resolve()),'path_key':rows[current]['path_key'] if rows else 'empty',
                         'title':'Menu usability · isolated fixture','year':'2026','media_type':media_type},
                  queue={'title':'Harbor Signals · اختبار', 'items':rows,'current_index':current, 'error':error},
                  start_position_ms=resume,
                  preferences={**safe_player_preferences(default_player_config()),'autoplay':autoplay})
        wait_for(lambda:any(e.get('type')=='ready' for e in self.events[before:]),'accepted load',10)
        wait_for(lambda:any(e.get('type')=='playback.state' and e.get('state')==('paused' if resume else 'playing')
                            for e in self.events[before:]),'file loaded',10)
        move_window_fraction(self.hwnd,.11 + (self.generation%2)*.02,.4)
        time.sleep(.5)

    def buttons(self):
        return [e for e in self.win.descendants(control_type='Button') if e.is_visible()]

    def button(self, name, contains=False):
        matches=[e for e in self.buttons() if (name in e.window_text() if contains else name==e.window_text())]
        if len(matches)!=1: raise AssertionError(f'{name!r}: {len(matches)} matches; {[e.window_text() for e in self.buttons()]}')
        return matches[0]

    def click(self, name, contains=False):
        target = self.button(name,contains)
        target.click_input()
        time.sleep(.2)

    def key(self, code):
        send_window_key(self.hwnd,code)
        time.sleep(.65) # Wait for a preceding completed click dismissal guard, including Escape.

    def capture(self, label):
        capture_window(self.hwnd,self.output/(label+'.png'))
        (self.output/(label+'-buttons.json')).write_text(json.dumps([
            {'name':e.window_text(),'rect':[e.rectangle().left,e.rectangle().top,e.rectangle().right,e.rectangle().bottom]} for e in self.buttons()],ensure_ascii=False,indent=2),encoding='utf-8')

    def dismiss(self, label, aim=(.12,.45)):
        before=len(self.events)
        progress=[e for e in self.events if e['type']=='progress']
        start_position=progress[-1]['position_ms'] if progress else None
        began=time.monotonic()
        self.capture(label+'-open')
        click_window_fraction(self.hwnd,*aim)
        time.sleep(.8)
        self.capture(label+'-dismissed')
        unexpected=[e for e in self.events[before:] if e['type'] in {'queue.select','resume.choice','playback.settings'}
                    or (e['type']=='playback.state' and e.get('state')=='paused')]
        assert not unexpected, (label,'outside click activated playback',unexpected)
        positions=[e['position_ms'] for e in self.events[before:] if e['type']=='progress']
        if start_position is not None and positions:
            tolerance=5000 + int((time.monotonic()-began)*1000)
            assert abs(positions[-1]-start_position)<tolerance,(label,'outside click sought',start_position,positions[-1])
        assert self.p.poll() is None

    def close(self):
        try:
            self.closing = True
            if self.p.poll() is None: self.send('close'); self.p.wait(8)
        finally:
            self.stop.set(); self.reader.join(1); self.tr.close(); self.log.close()
            if self.p.poll() is None: self.p.terminate(); self.p.wait(5)
            # Authentication hello contains a secret; never persist it.
            safe=[{k:v for k,v in e.items() if k not in {'token','session_token'}} for e in self.events if e['type']!='hello']
            (self.output/'events.json').write_text(json.dumps(safe,ensure_ascii=False,indent=2),encoding='utf-8')


def tv_rows():
    return [{'path_key':f's{s}e{e}', 'title':f'S{s:02d}E{e:02d} · Synthetic episode · الحلقة',
             'section':f'Season {s}','available':e!=19,'reason':'Missing locally' if e==19 else ''}
            for s in range(1,7) for e in range(1,21)]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--runtime',type=Path,required=True)
    parser.add_argument('--fixtures',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--scale',type=float,default=1.5)
    parser.add_argument('--actions-only', action='store_true')
    parser.add_argument('--playlist-only', action='store_true')
    parser.add_argument('--autoplay-case', choices=['cancel','playnow','natural'])
    parser.add_argument('--chrome-case', choices=['title','minimize','close'])
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    assert (args.fixtures/'menu.mkv').is_file(), 'Supply synthetic menu.mkv'
    session=Session(args.runtime.resolve(),args.fixtures.resolve(),args.output.resolve(),args.scale)
    checks=[]
    try:
        one=[{'path_key':'one','title':'One movie','section':'2026','available':True}]
        if args.autoplay_case:
            pair=one+[{'path_key':'two','title':'Two movie','section':'2026','available':True}]
            session.load(pair,autoplay=True,media_file='short.mp4')
            wait_for(lambda:any(e.window_text()=='Play now' for e in session.buttons()),'actual EOF countdown',8)
            session.capture('actual-eof-up-next')
            assert any(e['type']=='playback.state' and e.get('state')=='ended' for e in session.events)
            before=len(session.events)
            if args.autoplay_case=='cancel':
                session.click('Cancel')
                time.sleep(5.5)
                assert not any(e['type']=='queue.select' for e in session.events[before:]),'Cancel still advanced'
            else:
                if args.autoplay_case=='playnow': session.click('Play now')
                event=wait_for(lambda:next((e for e in session.events[before:] if e['type']=='queue.select'),None),'EOF progression',7)
                assert event['path_key']=='two' and event['automatic'],event
            print(json.dumps({'ok':True,'autoplay_case':args.autoplay_case}),flush=True)
            return
        if args.actions_only:
            session.load(one)
            def selected(kind):
                tracks=next((e['tracks'] for e in reversed(session.events) if e['type']=='tracks.changed'),[])
                return next((r['fingerprint'] for r in tracks if r['type']==kind and r.get('selected')),None)
            old_audio=selected('audio')
            session.key(0x41)
            matches=[e for e in session.buttons() if 'AAC' in e.window_text()]
            assert len(matches)>=2,'Long audio rows missing'
            matches[1].click_input()
            wait_for(lambda:selected('audio') and selected('audio')!=old_audio,'audio row selects a different real track')
            old_sub=selected('sub')
            session.key(0x53)
            matches=[e for e in session.buttons() if 'Subtitle ' in e.window_text()]
            assert len(matches)>=2,'Long subtitle rows missing'
            matches[1].click_input()
            wait_for(lambda:selected('sub') and selected('sub')!=old_sub,'subtitle row selects a different real track')
            session.key(0x43)
            before=len(session.events)
            session.click('Chapter 04',True)
            wait_for(lambda:any(e['type']=='progress' and 11500 <= e['position_ms'] <= 16000 for e in session.events[before:]),'chapter seeks to 12 seconds')
            session.click('Playback speed',True)
            session.click('2.00',True)
            assert any('Playback speed 2.00' in e.window_text() for e in session.buttons()),'Speed preset did not apply'
            session.capture('audio-subtitle-chapter-speed-selected')
            session.key(0x1B)
            print(json.dumps({'ok':True,'actions':['audio','subtitle','chapter','speed']}),flush=True)
            return
        if args.chrome_case:
            session.load(one+[{'path_key':'two','title':'Two','section':'2026','available':True}])
            session.click('Settings')
            from pywinauto import mouse
            rect=session.win.rectangle()
            if args.chrome_case=='title':
                from ctypes import wintypes
                api=ctypes.WinDLL('user32')
                api.SendMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
                api.SendMessageW.restype=ctypes.c_ssize_t
                x=rect.left+rect.width()//2; y=rect.top+30
                hit=api.SendMessageW(session.hwnd,0x0084,0,(y<<16)|(x&0xffff))
                assert hit==1,('Menu title strip must be HTCLIENT, not HTCAPTION',hit)
                click_window_fraction(session.hwnd,.5,30/rect.height())
                time.sleep(.8)
                assert len([e for e in session.buttons() if e.window_text()=='Close'])==1,'Title strip click did not dismiss Settings'
                session.click('Settings')
                mouse.double_click(coords=(x,y))
                time.sleep(.8)
                assert session.win.rectangle()==rect,'Title strip double click changed window geometry'
            else:
                name='Minimize' if args.chrome_case=='minimize' else 'Close'
                buttons=[e for e in session.buttons() if e.window_text()==name]
                target=min(buttons,key=lambda e:e.rectangle().top)
                r=target.rectangle()
                mouse.double_click(coords=((r.left+r.right)//2,(r.top+r.bottom)//2))
                time.sleep(.8)
                assert session.p.poll() is None,'Outside double click closed the player'
                assert not ctypes.windll.user32.IsIconic(session.hwnd),'Outside double click minimized the player'
                session.capture('window-'+args.chrome_case+'-double-click-consumed')
            print(json.dumps({'ok':True,'chrome_case':args.chrome_case,'scale':args.scale}),flush=True)
            return
        session.load(one)
        session.capture('singleton')
        assert not any(e.window_text()=='Playlist' for e in session.buttons()),'Singleton playlist button must be hidden'
        checks.append('singleton button hidden')
        session.load([])
        assert not any(e.window_text()=='Playlist' for e in session.buttons()),'Empty queue button must be hidden'
        checks.append('empty button hidden')
        pair=one+[{'path_key':'two','title':'Two movie','section':'2026','available':True}]
        session.load(pair,1)
        session.click('Playlist')
        assert any('One movie' in e.window_text() for e in session.buttons())
        assert any('Two movie' in e.window_text() for e in session.buttons())
        session.dismiss('movie-last-item')
        checks.append('last item retains both collection rows')
        session.load(tv_rows(),22,'tv')
        session.click('Playlist')
        names=[e.window_text() for e in session.buttons()]
        session.capture('tv-playing-season')
        assert any('S02E03' in n for n in names),names
        assert any('S02E03' in n for n in names) and not any('S01E01' in n for n in names),names
        session.capture('tv-playing-season')
        from pywinauto import mouse
        rect=session.win.rectangle()
        mouse.scroll(coords=(rect.right-int(100*args.scale),rect.top+int(250*args.scale)),wheel_dist=-35)
        time.sleep(.3)
        session.capture('tv-before-season6-click')
        session.click('Season 6')
        session.capture('tv-after-season6-click')
        assert not any('S02E03' in e.window_text() for e in session.buttons())
        # Scroll the actual pane until its last row is physically reachable.
        from pywinauto import mouse
        target=None
        rect=session.win.rectangle()
        for _ in range(10):
            matches=[e for e in session.buttons() if 'S06E20' in e.window_text()]
            target=matches[0] if matches else None
            r=target.rectangle() if target else None
            if r and r.bottom < rect.bottom - 220*args.scale and r.top > rect.top+110*args.scale: break
            mouse.scroll(coords=(rect.right-int(100*args.scale),rect.top+int(250*args.scale)),wheel_dist=-4)
            time.sleep(.1)
        time.sleep(.8) # Qt wheel deceleration consumes a click while it is still moving.
        target=session.button('S06E20',True)
        session.capture('tv-season6-bottom')
        before=len(session.events)
        target.click_input()
        session.capture("tv-after-episode-click")
        selection=wait_for(lambda:next((e for e in session.events[before:] if e['type']=='queue.select'),None),'S06E20 selection')
        assert selection['path_key']=='s6e20' and not selection['automatic'],selection
        session.send('queue.error',message='Offline fixture: selection unavailable')
        time.sleep(.65) # Let the completed selection gesture's double-click guard expire.
        session.click('Playlist')
        assert any('S02E03' in e.window_text() for e in session.buttons())
        session.key(0x1B)
        session.load(tv_rows(),119,'tv')
        session.click('Playlist')
        assert any('S06E20' in e.window_text() for e in session.buttons())
        session.dismiss('tv-new-playing-season')
        checks.append('six seasons, original key S06E20, failed switch and reopen, successful switch')
        missing=one+[{'path_key':'missing','title':'Missing member','section':'2026','available':False,'reason':'Missing locally'}]
        session.load(missing)
        session.click('Playlist')
        assert any('Missing member' in e.window_text() for e in session.buttons())
        session.capture('unavailable-member')
        session.key(0x1B)
        checks.append('missing membership retained')
        if args.playlist_only:
            print(json.dumps({'ok':True,'checks':checks,'scale':args.scale}),flush=True)
            return
        # Actual ordinary menus: playing and paused. No clicks may reach playback.
        for paused in [False,True]:
            if paused: session.key(0x20)
            for label,key in [('audio',0x41),('subtitles',0x53),('chapters',0x43),('statistics',0x49),('search',0x44)]:
                session.key(key)
                if label=='search':
                    session.capture('search-loading-'+str(paused))
                    session.send('subtitle.results',media_generation=session.generation,status='complete',results=[])
                    time.sleep(.1)
                    session.capture('search-empty-'+str(paused))
                    session.send('subtitle.results',media_generation=session.generation,status='error',results=[],error='Offline fixture')
                    time.sleep(.1)
                    session.capture('search-error-'+str(paused))
                    session.send('subtitle.results',media_generation=session.generation,status='complete',results=[
                        {'result_id':str(i),'provider':'fixture-offline','language':'ar','release_name':f'{i:02d} Long release name · العربية · '+ 'Long name ' * 18,
                         'file_name':f'{i}.srt','match_reason':'Synthetic match'} for i in range(40)])
                    time.sleep(.2)
                    session.capture('search-populated-'+str(paused))
                    from pywinauto import mouse
                    rect=session.win.rectangle()
                    mouse.scroll(coords=(rect.left+int(600*args.scale),rect.top+int(400*args.scale)),wheel_dist=-35)
                    time.sleep(.2)
                    session.capture('search-bottom-'+str(paused))
                    time.sleep(.1)
                if label in {'audio','subtitles','chapters'}:
                    from pywinauto import mouse
                    rect=session.win.rectangle()
                    session.capture(label+'-long-top-'+str(paused))
                    mouse.scroll(coords=(rect.right-int(150*args.scale),rect.bottom-int(300*args.scale)),wheel_dist=-35)
                    time.sleep(.8)
                    session.capture(label+'-long-bottom-'+str(paused))
                # Preserve paused state too: a leak would emit playing.
                before=len(session.events)
                session.dismiss(f'{label}-'+('paused' if paused else 'playing'))
                states=[e.get('state') for e in session.events[before:] if e['type']=='playback.state']
                assert not states,(label,states)
            session.click('Settings')
            session.dismiss('settings-'+('paused' if paused else 'playing'),aim=(.12,.45))
            session.click('Settings')
            # Help action may be below the side viewport; scroll to the end.
            from pywinauto import mouse
            rect=session.win.rectangle()
            mouse.scroll(coords=(rect.right-int(160*args.scale),rect.top+int(300*args.scale)),wheel_dist=-35)
            time.sleep(.8)
            session.click('Keyboard shortcuts',True)
            session.capture('help-'+('paused' if paused else 'playing'))
            session.click('Back')
            assert any('Autoplay next file' in e.window_text() for e in session.buttons())
            session.key(0x1B)
            session.click('Playback speed',True)
            assert any('2.00' in e.window_text() and 'Playback' not in e.window_text() for e in session.buttons()), 'Speed popup did not open'
            session.dismiss('speed-'+('paused' if paused else 'playing'))
        # A real double click must not reach the video's pause/fullscreen gestures.
        session.click('Playlist')
        from pywinauto import mouse
        rect=session.win.rectangle()
        before=len(session.events)
        mouse.double_click(coords=(rect.left+int(rect.width()*.12),rect.top+int(rect.height()*.45)),)
        time.sleep(.8)
        assert session.win.rectangle()==rect,'Outside double click changed window/fullscreen'
        assert not any(e['type']=='playback.state' for e in session.events[before:]),'Outside double click changed pause state'
        session.capture('outside-double-click-consumed')
        # An outside click on the timeline must not seek.
        session.click('Settings')
        session.dismiss('timeline-no-seek',aim=(.5,.884))
        checks.append('all ordinary menus outside click preserves playing/paused state; help Back and Escape; double click and timeline click consumed')
        session.load(one,resume=4000)
        before=len(session.events)
        click_window_fraction(session.hwnd,.12,.45)
        time.sleep(.6)
        assert any('Resume from' in e.window_text() for e in session.buttons())
        assert not any(e['type']=='resume.choice' for e in session.events[before:])
        session.capture('resume-undismissed')
        session.click('Start over')
        checks.append('resume outside click preserved; Start over works')
        errors=[e for e in session.events if e['type'] in {'error','reader.error'}]
        assert not errors,errors
        print(json.dumps({'ok':True,'checks':checks,'scale':args.scale,'pid':session.p.pid}),flush=True)
    except Exception:
        if session.p.poll() is None and not ctypes.windll.user32.IsIconic(session.hwnd):
            session.capture("failure")
        raise
    finally: session.close()

if __name__=='__main__': main()
