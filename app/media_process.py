"""Monotonic total deadline and cancellation for a direct media subprocess.

Not a process-tree sandbox. Stderr is spooled, never sent to an API response.
"""
import subprocess
import tempfile
import time


class MediaCancelled(RuntimeError):
    pass


class MediaStopped(RuntimeError):
    pass


class MediaDeadline(RuntimeError):
    pass


def check_deadline(deadline, check):
    check()
    if time.monotonic() >= deadline:
        raise MediaDeadline('任务总时限已到；可重试或调整服务端预算')


def run_process(command, deadline, check):
    check_deadline(deadline, check)
    with tempfile.TemporaryFile() as log:
        child = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=log)
        try:
            while child.poll() is None:
                check_deadline(deadline, check)
                time.sleep(.05)
            check_deadline(deadline, check)
            if child.returncode:
                raise RuntimeError('媒体无法解码或转码失败；请检查原视频编码')
            if log.tell() > 256 * 1024:
                raise RuntimeError('媒体诊断日志超过读取预算')
            log.seek(0)
            return log.read()
        finally:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=2)
            else:
                child.wait()
