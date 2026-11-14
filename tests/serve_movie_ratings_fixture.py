"""Disposable real ratings service + compiled UI; no external provider or CP data."""
import sys
import tempfile
import argparse
import time
import uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from flask import Flask, request, jsonify, send_from_directory, make_response
from services.movie_ratings import MovieRatingsService
from services.movie_ratings_store import MovieRatingsStore
from services.movie_ratings_routes import register_movie_ratings_routes

root=tempfile.TemporaryDirectory(prefix='cp-rt-browser-')
state={'connected':True,'owned':True,'calls':0,'delay':0,'available':True,'active':0,'metadata_calls':0}
dist=Path(__file__).resolve().parents[1]/'rt-candidate-dist'
def plex_movie(ident):
    return {'type':'movie','guid':'plex://movie/'+f'{int(ident):024x}',
        'Guid':[{'id':'tmdb://'+ident}], 'rating':5.9,'ratingImage':'rottentomatoes://image.rating.rotten',
        'audienceRating':6,'audienceRatingImage':'rottentomatoes://image.rating.upright'}
def transport(base,token,path,**kwargs):
    state['calls']+=1
    if not state['available']:raise OSError('Synthetic Plex outage')
    if path=='/library/sections':return {'MediaContainer':{'Directory':[]}}
    state['metadata_calls']+=1
    if state['delay']:
        state['active']+=1
        try:time.sleep(state['delay'])
        finally:state['active']-=1
    ident=str(kwargs.get('params',{}).get('guid','tmdb://44012')).split('//')[-1]
    if path.startswith('/library/metadata/') and not path.endswith('/matches'):ident='44012'
    return {'MediaContainer':{'Metadata':[plex_movie(ident)]}}
def new_service():
    return MovieRatingsService(MovieRatingsStore(Path(root.name)/(uuid.uuid4().hex+'.sqlite')),
        config=lambda:{'url':'http://synthetic-plex','token':'fixture'} if state['connected'] else {},
        ownership=lambda ids:{i['key']:{'rating_key':'42'} for i in ids if i.get('tmdb_id')=='44012' and state['owned']},transport=transport)
service=new_service()
app=Flask(__name__)
register_movie_ratings_routes(app,lambda:service)
@app.route('/fixture/control',methods=['POST'])
def control():
    global service
    if request.json.get('fresh'):
        service.stop()
        service=new_service()
        state['calls']=0
        state['metadata_calls']=0
    state.update({k:v for k,v in request.json.items() if k in ('connected','owned','delay','available')})
    service.invalidate_config()
    if request.json.get('warm'):
        service.store.publish([service._record(plex_movie(str(n)), 'local_saved' if n==44012 else 'online_cache') for n in range(44012,44052)])
    return jsonify(state)
@app.route('/fixture/state')
def current():return jsonify(state)
def card(ident):
    return {'tmdb_id':str(ident),'title':'Jeanne Dielman, 23 quai du Commerce, 1080 Bruxelles' if int(ident)==44012 else 'Ratings fixture '+str(ident),
        'year':'1975','genres':['Drama'],'tmdb_rating':'7.8','tmdb_vote_count':1234567,
        'poster_url':'/fixture/posters/'+str(ident)+'.svg','backdrop_url':'',
        'summary':'Synthetic movie metadata with existing actions and card controls.',
        'cast':[],'directors':[],'collection':{},'recommendations':[],'similar':[]}
@app.route('/fixture/posters/<ident>.svg')
def poster(ident):
    response=make_response('<svg xmlns="http://www.w3.org/2000/svg" width="340" height="510"><rect width="340" height="510" fill="#293845"/></svg>')
    response.mimetype='image/svg+xml';response.headers['Cache-Control']='public, max-age=3600'
    response.set_etag('ratings-fixture-poster')
    return response.make_conditional(request)
@app.route('/api/<path:path>',methods=['GET','POST'])
def fixture_api(path):
    if path.startswith('tmdb/discover'):return jsonify({'results':[card(n) for n in range(44012,44052)],'page':1,'total_pages':1,'total_results':40})
    if path=='tmdb/details':return jsonify(card(request.args.get('tmdb_id','44012')))
    if path=='tmdb/card-projections':return jsonify({'items':{},'catalog_generation':1})
    if path=='user/lists':return jsonify({'lists':[],'curation_generation':1})
    if path.startswith('user/followed-releases'):return jsonify({'movies':[],'curation_generation':1})
    if path=='library/check':return jsonify({'results':[],'catalog_generation':1})
    if path=='notifications':return jsonify({'items':[],'unread':0,'total':0,'total_pages':1})
    if path=='tv/capabilities':return jsonify({'enabled':False})
    if path=='ai/config':return jsonify({'provider':'ollama','features':[],'generation':1})
    if path=='movie-awards/snapshot':return jsonify({'schema_version':1,'awards_generation':1,'snapshot_owner':'fixture','ready':True,'movies':{},'people':{}})
    if path=='catalog/events':return ': fixture\n\n',200,{'Content-Type':'text/event-stream'}
    return jsonify({'items':[],'results':[]})
@app.route('/',defaults={'path':''})
@app.route('/<path:path>')
def compiled_ui(path):
    asset=path if (dist/path).is_file() else 'index.html'
    return send_from_directory(dist,asset,max_age=0 if asset=='index.html' else 3600)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=5130);parser.add_argument('--dist',type=Path,default=dist)
    args=parser.parse_args();dist=args.dist.resolve()
    try:app.run(host='127.0.0.1',port=args.port,threaded=True,use_reloader=False)
    finally:service.stop();root.cleanup()
