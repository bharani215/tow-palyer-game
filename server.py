from flask import Flask, render_template, request as flask_request
from flask_socketio import SocketIO, emit, join_room
import random, string

app = Flask(__name__)
app.config['SECRET_KEY'] = 'gamearena2024'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

rooms = {}

WORDS = ["cat","sun","tree","house","car","fish","moon","star","book","chair",
         "phone","pizza","apple","guitar","cloud","rocket","robot","dragon",
         "flower","mountain","umbrella","clock","bridge","lion","cake"]

RPS_BEATS = {"rock":"scissors","scissors":"paper","paper":"rock"}
WIN_LINES = [[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]]

def make_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))

def check_xox(board):
    for a,b,c in WIN_LINES:
        if board[a] and board[a]==board[b]==board[c]:
            return board[a],[a,b,c]
    if all(board):
        return "draw",[]
    return None,None

def end_game(code, winner):
    room = rooms.get(code)
    if not room: return
    socketio.emit('game_over', {
        'winner': winner,
        'bet': room['bet'],
        'scores': room['state'].get('scores', {'host':0,'guest':0}),
        'host_name': room['host']['name'],
        'guest_name': room['guest']['name'] if room['guest'] else '',
        'host_emoji': room['host']['emoji'],
        'guest_emoji': room['guest']['emoji'] if room['guest'] else '',
    }, room=code)

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('create_room')
def on_create(data):
    code = make_code()
    while code in rooms:
        code = make_code()
    rooms[code] = {
        'code': code, 'game': data['game'],
        'bet': int(data.get('bet', 0)),
        'host': {'sid': flask_request.sid, 'name': data['name'], 'emoji': data['emoji']},
        'guest': None, 'state': {}
    }
    join_room(code)
    emit('room_created', {'code': code, 'game': data['game'], 'bet': data.get('bet', 0)})

@socketio.on('join_room_req')
def on_join(data):
    code = data['code'].upper().strip()
    if code not in rooms:
        emit('error_msg', {'msg': '❌ Room not found!'}); return
    room = rooms[code]
    if room['guest']:
        emit('error_msg', {'msg': '❌ Room is full!'}); return
    room['guest'] = {'sid': flask_request.sid, 'name': data['name'], 'emoji': data['emoji']}
    join_room(code)
    socketio.emit('room_joined', {
        'code': code, 'game': room['game'], 'bet': room['bet'],
        'host': {'name': room['host']['name'], 'emoji': room['host']['emoji']},
        'guest': {'name': room['guest']['name'], 'emoji': room['guest']['emoji']},
    }, room=code)

@socketio.on('start_game')
def on_start(data):
    code = data['code']
    room = rooms.get(code)
    if not room or not room['guest']: return
    game = room['game']
    if game == 'rps':
        room['state'] = {'round':1,'max_rounds':5,'picks':{},'scores':{'host':0,'guest':0}}
        socketio.emit('rps_start', {
            'round':1,'max_rounds':5,
            'host_name':room['host']['name'],'host_emoji':room['host']['emoji'],
            'guest_name':room['guest']['name'],'guest_emoji':room['guest']['emoji'],
        }, room=code)
    elif game == 'xox':
        room['state'] = {'board':[None]*9,'turn':'host','scores':{'host':0,'guest':0}}
        socketio.emit('xox_start', {
            'board':[None]*9,'turn':'host',
            'host_name':room['host']['name'],'host_emoji':room['host']['emoji'],
            'guest_name':room['guest']['name'],'guest_emoji':room['guest']['emoji'],
        }, room=code)
    elif game == 'draw':
        drawer = random.choice(['host','guest'])
        word = random.choice(WORDS)
        room['state'] = {
            'round':1,'max_rounds':3,'drawer':drawer,'word':word,
            'scores':{'host':0,'guest':0},'guessed':False,'timer':60
        }
        d_sid = room['host']['sid'] if drawer=='host' else room['guest']['sid']
        g_sid = room['guest']['sid'] if drawer=='host' else room['host']['sid']
        d_name = room['host']['name'] if drawer=='host' else room['guest']['name']
        g_name = room['guest']['name'] if drawer=='host' else room['host']['name']
        socketio.emit('draw_start', {
            'role':'drawer','word':word,'round':1,'max_rounds':3,
            'drawer_name':d_name,'guesser_name':g_name,'scores':room['state']['scores']
        }, to=d_sid)
        socketio.emit('draw_start', {
            'role':'guesser','word_len':len(word),'round':1,'max_rounds':3,
            'drawer_name':d_name,'guesser_name':g_name,'scores':room['state']['scores']
        }, to=g_sid)

@socketio.on('rps_pick')
def on_rps(data):
    code=data['code']; role=data['role']; choice=data['choice']
    room=rooms.get(code)
    if not room: return
    st=room['state']
    st['picks'][role]=choice
    other = room['guest']['sid'] if role=='host' else room['host']['sid']
    socketio.emit('rps_opponent_picked', {}, to=other)
    if 'host' in st['picks'] and 'guest' in st['picks']:
        hp,gp=st['picks']['host'],st['picks']['guest']
        if hp==gp: result='draw'
        elif RPS_BEATS[hp]==gp: result='host'; st['scores']['host']+=1
        else: result='guest'; st['scores']['guest']+=1
        socketio.emit('rps_result', {
            'host_pick':hp,'guest_pick':gp,'result':result,
            'scores':st['scores'],'round':st['round']
        }, room=code)
        is_over = st['scores']['host']>=3 or st['scores']['guest']>=3 or st['round']>=st['max_rounds']
        if is_over:
            if st['scores']['host']>st['scores']['guest']: w='host'
            elif st['scores']['guest']>st['scores']['host']: w='guest'
            else: w='draw'
            end_game(code,w)
        else:
            st['round']+=1; st['picks']={}
            socketio.emit('rps_next_round',{'round':st['round']},room=code)

@socketio.on('xox_move')
def on_xox(data):
    code=data['code']; role=data['role']; idx=data['index']
    room=rooms.get(code)
    if not room: return
    st=room['state']
    if st['turn']!=role or st['board'][idx]: return
    sym='X' if role=='host' else 'O'
    st['board'][idx]=sym
    st['turn']='guest' if role=='host' else 'host'
    winner,line=check_xox(st['board'])
    socketio.emit('xox_update',{'board':st['board'],'index':idx,'symbol':sym,'turn':st['turn'],'winner':winner,'line':line},room=code)
    if winner:
        w='draw' if winner=='draw' else ('host' if winner=='X' else 'guest')
        end_game(code,w)

@socketio.on('draw_stroke')
def on_stroke(data):
    room=rooms.get(data['code'])
    if not room: return
    other=room['guest']['sid'] if data['role']=='host' else room['host']['sid']
    socketio.emit('draw_stroke',data,to=other)

@socketio.on('draw_clear')
def on_clear(data):
    room=rooms.get(data['code'])
    if not room: return
    other=room['guest']['sid'] if data['role']=='host' else room['host']['sid']
    socketio.emit('draw_clear',{},to=other)

@socketio.on('draw_guess')
def on_guess(data):
    code=data['code']; guess=data['guess'].strip().lower(); role=data['role']
    room=rooms.get(code)
    if not room: return
    st=room['state']
    if st.get('guessed') or role==st['drawer']: return
    name=room['host']['name'] if role=='host' else room['guest']['name']
    correct=guess==st['word'].lower()
    socketio.emit('draw_chat',{'name':name,'guess':guess,'correct':correct},room=code)
    if correct:
        st['guessed']=True
        pts=max(10,st['timer']+10)
        st['scores'][role]+=pts; st['scores'][st['drawer']]+=15
        socketio.emit('draw_correct',{'guesser':name,'word':st['word'],'scores':st['scores'],'pts_guesser':pts,'pts_drawer':15},room=code)
        socketio.emit('draw_next_prompt',{},room=code)

@socketio.on('draw_timer_tick')
def on_tick(data):
    room=rooms.get(data['code'])
    if room: room['state']['timer']=data.get('timer',60)

@socketio.on('draw_round_end')
def on_round_end(data):
    code=data['code']; room=rooms.get(code)
    if not room: return
    st=room['state']
    if st['round']>=st['max_rounds']:
        hs=st['scores']['host']; gs=st['scores']['guest']
        w='host' if hs>gs else 'guest' if gs>hs else 'draw'
        end_game(code,w)
    else:
        st['round']+=1; st['guessed']=False; st['timer']=60
        st['drawer']='guest' if st['drawer']=='host' else 'host'
        word=random.choice(WORDS); st['word']=word
        drawer=st['drawer']
        d_sid=room['host']['sid'] if drawer=='host' else room['guest']['sid']
        g_sid=room['guest']['sid'] if drawer=='host' else room['host']['sid']
        d_name=room['host']['name'] if drawer=='host' else room['guest']['name']
        g_name=room['guest']['name'] if drawer=='host' else room['host']['name']
        socketio.emit('draw_start',{'role':'drawer','word':word,'round':st['round'],'max_rounds':st['max_rounds'],'drawer_name':d_name,'guesser_name':g_name,'scores':st['scores']},to=d_sid)
        socketio.emit('draw_start',{'role':'guesser','word_len':len(word),'round':st['round'],'max_rounds':st['max_rounds'],'drawer_name':d_name,'guesser_name':g_name,'scores':st['scores']},to=g_sid)

@socketio.on('rematch')
def on_rematch(data):
    code=data['code']; room=rooms.get(code)
    if not room: return
    if '_rematch' not in room: room['_rematch']=set()
    room['_rematch'].add(data['role'])
    other=room['guest']['sid'] if data['role']=='host' else room['host']['sid']
    socketio.emit('opponent_rematch',{},to=other)
    if len(room['_rematch'])==2:
        room['_rematch']=set()
        on_start({'code':code})

@socketio.on('disconnect')
def on_disconnect():
    sid=flask_request.sid
    for code,room in list(rooms.items()):
        if room['host']['sid']==sid:
            socketio.emit('opponent_left',{'name':room['host']['name']},room=code)
            del rooms[code]; break
        elif room['guest'] and room['guest']['sid']==sid:
            socketio.emit('opponent_left',{'name':room['guest']['name']},room=code)
            room['guest']=None; break

if __name__=='__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
