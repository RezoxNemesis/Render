"""Run the production HTTPS source guard through real JDK URL/IP parsers.

No Android SDK, network requests or mocked Java parsing are involved.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'app/src/main/java/com/rezox/render/agent/FileTransferSources.java'


@unittest.skipUnless(shutil.which('java'),'JDK is required for Java source policy checks')
class TransferSourcePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        runner=Path(cls.temp.name)/'SourcePolicyProbe.java'
        runner.write_text('''package com.rezox.render.agent;
public class SourcePolicyProbe {
    public static void main(String[] args)throws Exception {
        for(int i=1;i<args.length;i++) {
            boolean rejected=false;
            try { FileTransferSources.checked(args[i]); }
            catch(IllegalArgumentException error) {
                if(!"LOCAL_NETWORK_SOURCE_UNAVAILABLE".equals(error.getMessage()))throw error;
                rejected=true;
            }
            if(rejected!=args[0].equals("reject"))
                throw new AssertionError("Unexpected URL policy result: "+args[i]);
        }
    }
}''',encoding='utf8')
        compile_command=['java','-m','jdk.compiler/com.sun.tools.javac.Main',
                         '-d',cls.temp.name,str(SOURCE),str(runner)]
        result=subprocess.run(compile_command,capture_output=True,text=True,timeout=30)
        if result.returncode:
            raise AssertionError('Java policy compile failed: '+result.stderr)

    def check_urls(self,mode,urls):
        result=subprocess.run(['java','-cp',self.temp.name,
            'com.rezox.render.agent.SourcePolicyProbe',mode,*urls],
            capture_output=True,text=True,timeout=15)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_bracketed_loopback_and_localhost_root_dot_are_blocked(self):
        self.check_urls('reject',['https://[::1]/file','https://localhost./file',
            'https://sub.localhost./file','https://127.0.0.1./file'])

    def test_private_link_local_and_unspecified_literals_are_blocked(self):
        self.check_urls('reject',['https://10.0.0.1/file','https://172.16.0.1/file',
            'https://172.31.255.254/file','https://192.168.1.1/file',
            'https://169.254.169.254/file','https://0.0.0.0/file',
            'https://100.64.0.1/file','https://[::]/file','https://[fe80::1]/file',
            'https://[fc00::1]/file','https://[fd12:3456::1]/file',
            'https://[fec0::1]/file','https://[::ffff:127.0.0.1]/file',
            'https://[::ffff:192.168.1.1]/file','https://[::127.0.0.1]/file',
            'https://[fe80::1%25wlan0]/file','https://224.0.0.1/file',
            'https://[ff02::1]/file'])

    def test_alternative_ipv4_spellings_cannot_bypass_literal_checks(self):
        self.check_urls('reject',['https://2130706433/file','https://127.1/file',
            'https://0177.0.0.1/file','https://0x7f000001/file',
            'https://0x7f.0.0.1/file','https://127.000.000.001/file'])

    def test_public_literals_and_unresolved_hostnames_remain_offline_queueable(self):
        self.check_urls('accept',['https://8.8.8.8/file','https://172.32.0.1/file',
            'https://[2606:4700:4700::1111]/file',
            'https://never-resolve-this.invalid/file?signature=fixture',
            'https://example.com./file'])


if __name__=='__main__':unittest.main()
