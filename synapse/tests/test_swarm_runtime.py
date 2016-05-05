import synapse.cortex as s_cortex
import synapse.daemon as s_daemon
import synapse.telepath as s_telepath
import synapse.lib.service as s_service
import synapse.lib.userauth as s_userauth
import synapse.swarm.runtime as s_runtime

from synapse.tests.common import *

class SwarmRunTest(SynTest):

    def getSwarmEnv(self):
        tenv = TestEnv()

        core0 = s_cortex.openurl('ram://')
        core1 = s_cortex.openurl('ram://')

        tenv.add('core0',core0,fini=True)
        tenv.add('core1',core1,fini=True)

        tufo0 = core0.formTufoByProp('foo:bar','baz',vvv='visi')
        tufo1 = core0.formTufoByProp('foo:bar','faz',vvv='visi')
        tufo2 = core1.formTufoByProp('foo:bar','lol',vvv='visi')
        tufo3 = core1.formTufoByProp('foo:bar','hai',vvv='visi')

        tufo4 = core0.formTufoByProp('zzz:woot',10,vvv='visi')
        tufo5 = core1.formTufoByProp('zzz:woot',12,vvv='romp')

        tenv.add('tufo0',tufo0)
        tenv.add('tufo1',tufo1)
        tenv.add('tufo2',tufo2)
        tenv.add('tufo3',tufo3)

        dmon = s_daemon.Daemon()
        link = dmon.listen('tcp://127.0.0.1:0')

        tenv.add('link',link)
        tenv.add('dmon',dmon,fini=True)

        port = link[1].get('port')

        svcbus = s_service.SvcBus()
        tenv.add('svcbus',svcbus,fini=True)

        dmon.share('syn.svcbus',svcbus)

        svcrmi = s_telepath.openurl('tcp://127.0.0.1/syn.svcbus', port=port)
        tenv.add('svcrmi',svcrmi,fini=True)

        s_service.runSynSvc('cortex',core0,svcrmi,tags=('hehe.haha',))
        s_service.runSynSvc('cortex',core1,svcrmi,tags=('hehe.hoho',))

        runt = s_runtime.Runtime(svcrmi)

        tenv.add('runt',runt,fini=True)

        return tenv

    def test_swarm_runtime_lift(self):
        tenv = self.getSwarmEnv()

        answ = tenv.runt.ask('foo:bar="baz"')
        data = answ.get('data')

        self.assertEqual( data[0][0], tenv.tufo0[0] )
        #print(answ)

        # FIXME check for other expected results info!

        answ = tenv.runt.ask('foo:bar:vvv')
        data = answ.get('data')

        self.assertEqual( len(data), 4 )

        tenv.fini()

    def test_swarm_runtime_pivot(self):
        tenv = self.getSwarmEnv()

        answ = tenv.runt.ask('foo:bar="baz" ^foo:bar:vvv')
        data = answ.get('data')

        self.assertEqual( len(data), 4 )

        answ = tenv.runt.ask('foo:bar="baz" ^foo:bar:vvv=foo:bar:vvv')
        data = answ.get('data')

        self.assertEqual( len(data), 4 )

        tenv.fini()

    def test_swarm_runtime_opts(self):
        tenv = self.getSwarmEnv()

        answ = tenv.runt.ask('%foo')
        self.assertEqual( answ['options'].get('foo'), 1 )

        answ = tenv.runt.ask('opts(foo=10)')
        self.assertEqual( answ['options'].get('foo'), 10 )

        answ = tenv.runt.ask('%foo=10')
        self.assertEqual( answ['options'].get('foo'), 10 )

        answ = tenv.runt.ask('opts(foo="bar")')
        self.assertEqual( answ['options'].get('foo'), 'bar' )

        answ = tenv.runt.ask('%foo="bar"')
        self.assertEqual( answ['options'].get('foo'), 'bar' )

        tenv.fini()

    def test_swarm_runtime_opts_uniq(self):
        tenv = self.getSwarmEnv()

        answ = tenv.runt.ask('%uniq foo:bar="baz" foo:bar="baz"')
        self.assertEqual( len(answ['data']), 1 )

        answ = tenv.runt.ask('%uniq=0 foo:bar="baz" foo:bar="baz"')
        self.assertEqual( len(answ['data']), 2 )

        tenv.fini()

    def test_swarm_runtime_userauth_form(self):
        tenv = self.getSwarmEnv()

        core = s_cortex.openurl('ram://')
        auth = s_userauth.UserAuth(core)

        auth.addUser('visi')
        tenv.runt.setUserAuth(auth)

        answ = tenv.runt.ask('foo:bar="baz"',user='visi')
        self.assertEqual( len(answ['data']), 0 )

        auth.addUserRule('visi','tufo.form.foo:*')

        answ = tenv.runt.ask('foo:bar="baz"',user='visi')
        self.assertEqual( len(answ['data']), 1 )

        auth.fini()
        core.fini()

        tenv.fini()

    def test_swarm_runtime_join(self):
        tenv = self.getSwarmEnv()

        #&zzz:woot:vvv=foo:bar:vvv

        answ = tenv.runt.ask('foo:bar="baz" &foo:bar:vvv')
        data = answ.get('data')

        self.assertEqual( len(data), 4 )

        answ = tenv.runt.ask('foo:bar="baz" &zzz:woot:vvv=foo:bar:vvv')
        data = answ.get('data')

        self.assertEqual( len(data), 2 )

        tenv.fini()
