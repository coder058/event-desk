"""Loopback-only TLS/HTTP multiplexing probe; production listeners stay untouched."""
from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path

from bootstrap import SSH

CONFIG = """global
    log stdout format raw local0
    maxconn 128
defaults
    log global
    option tcplog
    mode tcp
    timeout connect 5s
    timeout client 30s
    timeout server 30s
frontend shared_port
    bind :80
    tcp-request inspect-delay 5s
    tcp-request content accept if { req.ssl_hello_type 1 }
    tcp-request content accept if HTTP
    use_backend encrypted if { req.ssl_hello_type 1 }
    default_backend cleartext
backend encrypted
    server caddy caddy:443
backend cleartext
    server caddy caddy:80
"""
# SOURCE: HAProxy 3.2 official manual ClientHello/HTTP ACLs and Docker official image family.
# GUESS: 128 connections, 5/30-second bounds and 64 MiB are initial operational ceilings.
# UNCALIBRATED GUESS: not capacity or production-latency claims.
# GUESS: 18880 is an isolated loopback probe port. # UNCALIBRATED GUESS
REMOTE = '''
import json,subprocess,sys,time
from pathlib import Path
data=json.load(sys.stdin)
name='eventdesk-https-probe-'+str(time.time_ns())
root=Path('/srv/eventdesk/private');root.mkdir(mode=0o700,exist_ok=True)
# SOURCE: official container runs unprivileged; this static config has no secrets.
config=root/(name+'.cfg');config.write_text(data['config']);config.chmod(0o644)
docker=['sudo','docker'];image='haproxy:3.2-alpine'
network=json.loads(subprocess.check_output(docker+['inspect','--format','{{json .NetworkSettings.Networks}}','eventdesk-caddy-1']))
if set(network)!={'eventdesk_default'}: raise RuntimeError('Unexpected Caddy network')
try:
 subprocess.run(docker+['pull',image],capture_output=True,check=True)
 digest=json.loads(subprocess.check_output(docker+['inspect','--format','{{json .RepoDigests}}',image]))[0]
 mount='type=bind,source='+str(config)+',target=/usr/local/etc/haproxy/haproxy.cfg,readonly'
 checked=subprocess.run(docker+['run','--rm','--network','eventdesk_default','--mount',mount,digest,'haproxy','-c','-f','/usr/local/etc/haproxy/haproxy.cfg'],capture_output=True)
 if checked.returncode:
  print(json.dumps({'stage':'configuration_validation','diagnostic':checked.stderr.decode(errors='replace')}),flush=True)
  raise RuntimeError('Proxy configuration validation failed')
 subprocess.run(docker+['run','--rm','-d','--name',name,'--network','eventdesk_default','--memory','64m','-p','127.0.0.1:18880:80','--mount',mount,digest],capture_output=True,check=True)
 hostname='52.17.192.36.sslip.io'
 # SOURCE: curl --connect-to changes only transport destination, preserving verified certificate/SNI.
 # GUESS: bounded newly-started-container readiness retries, not webhook retries. # UNCALIBRATED GUESS
 base=['curl','--noproxy','*','--connect-to',hostname+':80:127.0.0.1:18880','--max-time','8','--retry','3','--retry-all-errors','--retry-delay','1','--retry-max-time','10','-sS']
 result=subprocess.run(base+['--fail','https://'+hostname+':80/healthz'],capture_output=True)
 if result.returncode:
  logs=subprocess.run(docker+['logs',name],capture_output=True)
  print(json.dumps({'stage':'verified_tls','diagnostic':result.stderr.decode(errors='replace'),'startup':logs.stderr.decode(errors='replace'),'routing':logs.stdout.decode(errors='replace')}),flush=True)
  raise RuntimeError('Loopback verified TLS probe failed')
 health=json.loads(result.stdout)
 if health.get('database')!='reachable' or health.get('fixture_mode') is not False: raise RuntimeError('Unexpected application behind proxy')
 rejected=subprocess.run(base+['-o','/dev/null','-w','%{http_code}','-X','POST','--data','{}','https://'+hostname+':80/competition/webhook'],capture_output=True,check=True).stdout.decode()
 clear=subprocess.run(base+['-o','/dev/null','-w','%{http_code}','http://'+hostname+':80/healthz'],capture_output=True,check=True).stdout.decode()
 if rejected!='401' or clear!='308': raise RuntimeError('Application signature/redirect checks failed')
 print(json.dumps({'image':digest,'tls_certificate_verified':True,'health_status':200,'unsigned_webhook_status':int(rejected),'plaintext_redirect_status':int(clear),'listener':'loopback_only','public_listeners_changed':False,'limits':'No portal delivery or public reachability is established by this probe'}))
finally:
 subprocess.run(docker+['rm','-f',name],capture_output=True)
 config.unlink(missing_ok=True)
'''


def main() -> None:
    result = subprocess.run(SSH+["sudo python3 -c "+shlex.quote(REMOTE)],
        input=json.dumps({"config": CONFIG}).encode(), capture_output=True)
    if result.returncode:
        # Only this probe's static public-host configuration is validated; diagnostic bytes stay private.
        Path("private/https-mux-probe-error.log").write_bytes(result.stdout+b"\n"+result.stderr)
        if result.stdout:
            diagnostic = json.loads(result.stdout)
            print(json.dumps({"failed_stage": diagnostic.get("stage")}))
        raise RuntimeError("Loopback proxy probe failed; raw diagnostic output withheld")
    report = json.loads(result.stdout)
    Path("reports/https-mux-probe.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
