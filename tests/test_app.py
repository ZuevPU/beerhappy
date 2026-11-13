import unittest, tempfile, threading, json, urllib.request, urllib.error, http.cookiejar, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
from domain import derangement,quiz

class Client:
    def __init__(self,url): self.url=url; self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def call(self,path,data=None,origin=None):
        req=urllib.request.Request(self.url+'/api'+path,data=json.dumps(data).encode() if data is not None else None,headers={'Origin':origin or self.url,'Content-Type':'application/json'})
        try:
            with self.opener.open(req) as r:return r.status,json.load(r)
        except urllib.error.HTTPError as e:return e.code,json.load(e)

class Pilot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(); server.DB=cls.temp.name+'/app.sqlite'; server.init()
        cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler); cls.url='http://127.0.0.1:'+str(cls.http.server_port); server.PUBLIC_URL=cls.url
        threading.Thread(target=cls.http.serve_forever,daemon=True).start()
    @classmethod
    def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();cls.temp.cleanup()
    def test_full_pilot(self):
        clients=[]
        for i in range(12):
            c=Client(self.url); status,_=c.call('/signup',{'email':f'u{i}@example.org','name':f'Друг {i}','password':'safe password 123','adult':True});self.assertEqual(status,200);clients.append(c)
        admin=clients[0]
        config={'name':'Пилот','delivery':'meeting','quantity_mode':'exact','quantity':6,'maximum':6,'budget_min':1000,'budget_max':2000,'methods':['manual','quiz','ai'],'participate':True}
        _,result=admin.call('/groups',config);g=result['id'];base='/groups/'+g
        _,detail=admin.call(base);invite=detail['invite']
        wish={'method':'manual','constraints':{'alcohol':'zero','max_abv':0,'no_bitter':True},'surprise':False,'items':[{'name':'Лагер 0,0%','count':6,'similar':True}],'comment':'Проверить этикетку','handoff':'Заберу на встрече'}
        for c in clients[:10]:
            self.assertEqual(c.call(base+'/join',{'invite':invite})[0],200)
            self.assertEqual(c.call(base+'/wish',wish)[0],200)
        self.assertEqual(clients[11].call(base)[0],403)
        self.assertEqual(clients[1].call(base+'/draw',{})[0],403)
        self.assertEqual(admin.call(base+'/wish',{**wish,'items':[{'name':'X','count':5}]})[0],400)
        self.assertEqual(admin.call(base+'/draw',{})[0],200)
        _,d=admin.call(base);pairs=d['pairs'];self.assertEqual(len(pairs),10)
        self.assertEqual(len({p['giver'] for p in pairs}),10);self.assertEqual(len({p['receiver'] for p in pairs}),10)
        self.assertTrue(all(p['giver']!=p['receiver'] for p in pairs))
        admin.call(base+'/draw',{});self.assertEqual(admin.call(base)[1]['pairs'],pairs)
        _,normal=clients[1].call(base);self.assertNotIn('pairs',normal);self.assertNotIn('members',normal);self.assertNotIn('invite',normal)
        self.assertNotIn('giver',normal['incoming']);self.assertNotIn('email',json.dumps(normal))
        _,rec=clients[1].call(base+'/recipient',{});self.assertEqual(rec['wish']['constraints']['alcohol'],'zero')
        self.assertEqual(clients[1].call(base+'/chat',{'direction':'outgoing','body':'Привет от Санты'})[0],200)
        idx=int(rec['name'].split()[-1]);_,msgs=clients[idx].call(base+'/chat/incoming');self.assertEqual(msgs[0]['body'],'Привет от Санты');self.assertNotIn('giver',msgs[0])
        self.assertTrue(clients[idx].call(base)[1]['viewed']);clients[idx].call(base+'/wish',wish);self.assertFalse(clients[idx].call(base)[1]['viewed'])
        clients[1].call(base+'/recipient',{});self.assertTrue(clients[idx].call(base)[1]['viewed'])
        # Late entrant can save wishes but cannot receive an assignment until admitted.
        late=clients[10];late.call(base+'/join',{'invite':invite});late.call(base+'/wish',wish)
        _,d=admin.call(base);entry=next(m for m in d['members'] if m['name']=='Друг 10');self.assertEqual(entry['status'],'pending')
        self.assertEqual(admin.call(base+'/admit',{'user_id':entry['id'],'after':pairs[0]['giver']})[0],200)
        _,d=admin.call(base);self.assertEqual(len(d['pairs']),11)
        self.assertEqual(len({p['receiver'] for p in d['pairs']}),11)
        # Find a legal swap and ensure old conversation disappears.
        a=next(p for p in d['pairs'] if p['giver_name']=='Друг 1')
        b=next(p for p in d['pairs'] if p['giver']!=a['giver'] and p['giver']!=a['receiver'] and p['receiver']!=a['giver'])
        self.assertEqual(admin.call(base+'/swap',{'a':a['giver'],'b':b['giver']})[0],200)
        self.assertEqual(clients[1].call(base+'/chat/outgoing')[1],[])
        # Hard constraints survive recommendation and cannot be bypassed by AI or CSRF.
        _,r=clients[1].call(base+'/quiz',{'route':'association','answers':{'music':1},'constraints':{'no_bitter':True,'alcohol':'zero','max_abv':0}})
        self.assertNotIn('ipa',[s['id'] for s in r['styles']]);self.assertEqual(r['constraints']['alcohol'],'zero')
        self.assertEqual(admin.call(base+'/rotate-invite',{},origin='https://evil.test')[0],403)
        self.assertEqual(admin.call(base+'/rotate-invite',{})[0],200)
        self.assertEqual(clients[11].call(base+'/join',{'invite':invite})[0],403)
        # Removing a participant preserves the remaining bijection and revokes access.
        _,d=admin.call(base)
        removing=next(m for m in d['members'] if m['name']=='Друг 10')
        self.assertEqual(admin.call(base+'/remove',{'user_id':removing['id']})[0],200)
        self.assertEqual(late.call(base)[0],403)
        _,d=admin.call(base); self.assertEqual(len(d['pairs']),10)
        self.assertTrue(all(p['giver']!=p['receiver'] for p in d['pairs']))
        self.assertEqual(len({p['receiver'] for p in d['pairs']}),10)
        self.assertEqual(admin.call(base+'/finish',{})[0],200)
        self.assertEqual(clients[1].call(base+'/wish',wish)[0],400)
    def test_algorithm(self):
        for n in range(3,51):
            pairs=derangement(list(range(n)));self.assertEqual(len(set(b for a,b in pairs)),n);self.assertTrue(all(a!=b for a,b in pairs))
        result=quiz({'bitter':0,'music':1},'mixed',{})
        self.assertTrue(result['constraints']['no_bitter']);self.assertNotIn('ipa',[s['id'] for s in result['styles']])
    def test_remove_mutual_pair(self):
        c=Client(self.url)
        self.assertEqual(c.call('/signup',{'email':'mutual@example.org','name':'M','password':'safe password 123','adult':True})[0],200)
        with server.db(True) as conn:
            uid=conn.execute("SELECT id FROM users WHERE email='mutual@example.org'").fetchone()[0]
            conn.execute('INSERT INTO groups(id,owner,invite,name,settings,state) VALUES(?,?,?,?,?,?)',('mutual',uid,'mutual','M','{}','drawn'))
            ids=[]
            for i in range(4):
                user='mutual'+str(i);ids.append(user)
                conn.execute('INSERT INTO users VALUES(?,?,?,?)',(user,user+'@example.org','M','unused'))
                conn.execute("INSERT INTO members(group_id,user_id,status,wish) VALUES('mutual',?,'active','{}')",(user,))
            for a,b in [(ids[0],ids[1]),(ids[1],ids[0]),(ids[2],ids[3]),(ids[3],ids[2])]:
                conn.execute("INSERT INTO pairs(id,group_id,giver,receiver) VALUES(?,'mutual',?,?)",(a,a,b))
        self.assertEqual(c.call('/groups/mutual/remove',{'user_id':ids[0]})[0],200)
        with server.db() as conn:
            rows=conn.execute("SELECT giver,receiver FROM pairs WHERE group_id='mutual' AND active=1").fetchall()
            self.assertEqual(len(rows),3);self.assertTrue(all(a!=b for a,b in rows));self.assertEqual(len({b for a,b in rows}),3)

    def test_concurrent_draw(self):
        # Race tested directly against the transactional database, with ready members.
        with server.db(True) as c:
            c.execute("INSERT INTO users VALUES('race','race@example.org','Race','unused')")
            c.execute("INSERT INTO groups(id,owner,invite,name,settings) VALUES('race','race','race','Race','{}')")
            for i in range(10):
                c.execute('INSERT INTO users VALUES(?,?,?,?)',(f'r{i}',f'r{i}@example.org','R','unused'))
                c.execute("INSERT INTO members(group_id,user_id,status,wish) VALUES('race',?,'active','{}')",(f'r{i}',))
        errors=[]
        def run():
            try:
                with server.db(True) as c:server.draw(c,'race')
            except Exception as e:errors.append(e)
        threads=[threading.Thread(target=run) for _ in range(5)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(errors,[])
        with server.db() as c:self.assertEqual(c.execute("SELECT count(*) FROM pairs WHERE group_id='race'").fetchone()[0],10)

if __name__=='__main__':unittest.main()
