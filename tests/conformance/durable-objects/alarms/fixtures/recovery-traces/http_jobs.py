#!/usr/bin/env python3
"""Bounded, private guest-side HTTP cohort. Imported by the concrete guest driver."""
import concurrent.futures, json, pathlib, threading, time, urllib.error, urllib.request
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): raise ValueError('redirect prohibited')
def run(jobs, destination):
    if not 1 <= len(jobs) <= 16: raise ValueError('cohort size exceeds bound')
    destination = pathlib.Path(destination)
    if destination.exists(): raise ValueError('result directory must be fresh')
    destination.mkdir()
    barrier = threading.Barrier(len(jobs))
    def call(job):
        if job['node'] not in (1, 2): raise ValueError('invalid private guest node')
        if not job['id'].isalnum(): raise ValueError('invalid job id')
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        barrier.wait(timeout=5)
        record = {'id': job['id'], 'started_ns': time.monotonic_ns()}
        try:
            request = urllib.request.Request('http://192.168.77.%s:18080/op' % job['node'], data=json.dumps(job['body']).encode(), headers={'Content-Type':'application/json'})
            try: response = opener.open(request, timeout=90)
            except urllib.error.HTTPError as error: response = error
            with response:
                raw = response.read(1048577)
                if len(raw) > 1048576: raise ValueError('response exceeds 1 MiB')
                record.update(status=response.status, body=json.loads(raw) if response.status == 200 else raw[:8192].decode(errors='replace'))
        except Exception as error: record['transport_error'] = repr(error)
        record['finished_ns'] = time.monotonic_ns()
        target = destination / (job['id'] + '.json'); temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps(record)); temporary.replace(target)
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        list(pool.map(call, jobs))
if __name__ == '__main__':
    import sys
    run(json.loads(pathlib.Path(sys.argv[1]).read_text()), sys.argv[2])
