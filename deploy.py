import sh
import sys


def deploy(host, command):
    def line(response, stdin):
        print("> ", response.rstrip())

    def error(response, stdin):
        print("! ", response.rstrip())

    def done(cmd, success, exit_code):
        print("Done: {!r}, {!r}".format(success, exit_code))

    try:
        sh.ssh(host, command, _out=line, _err=error, _done=done)

    except sh.ErrorReturnCode as e:
        print("Error during ssh:", e.exit_code)


if __name__ == '__main__':
    deploy(sys.argv[1], """
        cd src/werewolf && git pull && make build stop run
        """)
