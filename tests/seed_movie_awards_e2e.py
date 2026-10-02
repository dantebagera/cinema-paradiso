"""Synthetic awards only, installed inside the runner's isolated test root."""
import copy, hashlib, json, sys, tempfile
from pathlib import Path
from services.movie_awards_store import MovieAwardsStore
from tools.build_movie_awards_snapshot import canonical_bytes


def install(root):
    root=Path(root).resolve()
    if Path(tempfile.gettempdir()).resolve() not in root.parents:
        raise RuntimeError('Awards fixture requires an OS-temp test root')
    movies=[{'namespace':'movie','imdb_id':f'tt{i:07d}','tmdb_id':i,'evidence':{'revision':'synthetic-e2e'},
             'facts':{'title':f'Winning film {i}','release_date':'2024-01-01','genre_ids':[53]}} for i in [1,2,3,4,5]+list(range(30,150))]
    people=[{'namespace':'person','imdb_id':f'nm{i:07d}','tmdb_id':i,'evidence':{'revision':'synthetic-e2e'}} for i in [90,100,101]]
    film=lambda i:f'movie:imdb:tt{i:07d}'
    person=lambda i:f'person:imdb:nm{i:07d}'
    data={'schema_version':1,'identity_mappings':movies+people,'coverage':{},'ceremonies':[]}
    for org,offset in [('oscar',1928),('golden_globe',1943)]:
        data['coverage'][org]={'status':'complete','first_ceremony':1,'last_ceremony':3}
        for ceremony in range(1,4):
            wins=[{'person':person(100),'role':'actor','award_instance':'ACTOR','category':'ACTOR','films':[film(1),film(2)] if ceremony==1 else [film(1)],'evidence':[{'revision':'synthetic-winner'}]},
                  {'person':person(90),'role':'director','award_instance':'DIRECTOR','category':'DIRECTOR','films':[film(2)],'evidence':[{'revision':'synthetic-winner'}]}]
            films={film(1):4 if org=='oscar' else 1,film(2):2}
            if ceremony==1:
                wins.append({'person':person(100),'role':'director','award_instance':'DIRECTOR','category':'DIRECTOR','films':[film(3)],'evidence':[{'revision':'synthetic-winner'}]})
                films[film(3)]=1
                # Every matching film remains reachable, beyond the related-feed cap.
                wins.append({'person':person(101),'role':'actor','award_instance':'ACTOR','category':'ACTOR','films':[film(i) for i in range(30,150)],'evidence':[{'revision':'synthetic-winner'}]})
                films.update({film(i):1 for i in range(30,150)})
            data['ceremonies'].append({'organization':org,'ceremony':ceremony,'ceremony_year':offset+ceremony,'films':films,'person_wins':wins,
                'validation':{'evidence':{'revision':'synthetic-program'},'crosscheck':{'crosscheck_agrees':True,'revision':'synthetic-independent'}}})
    manifest={'schema_version':1,'ready':True,'seed_sha256':hashlib.sha256(canonical_bytes(data)).hexdigest()}
    MovieAwardsStore(root/'user-data/awards/awards.sqlite').install_seed(data,manifest)


if __name__=='__main__':install(sys.argv[1])
