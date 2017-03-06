import click
import subprocess
import sys
import re
import uuid
import rollbar


class LinuxRouter(object):
    def route_to_localhost(self, ip):
        # cast("sudo iptables -t nat -L OUTPUT")
        cast("sudo iptables -t nat -A OUTPUT -p all -d %(ip)s -j DNAT --to-destination 127.0.0.1" % {"ip": ip})
    def unroute_to_localhost(self, ip):
        cast("sudo iptables -t nat -D OUTPUT -p all -d %(ip)s -j DNAT --to-destination 127.0.0.1" % {"ip": ip})
        # cast("sudo iptables -t nat -L OUTPUT")

class DarwinRouter(object):
    def route_to_localhost(self, ip):
        """
        It's not great that we use "from any to any". It would be better to use
        from any to 10.244.7.124, but when I do that, erl fails to startup with
        Protocol 'inet_tcp': register/listen error: etimedout
        My guess is, it's trying to find epmd to register itself, but can't due to
        something in this file.
        """
        ps = subprocess.Popen(('echo', """
rdr pass on lo0 inet proto tcp from any to any port 4369 -> 127.0.0.1 port 4369
rdr pass on lo0 inet proto tcp from any to 10.244.7.124 port 36606 -> 127.0.0.1 port 36606
"""), stdout=subprocess.PIPE)
        subprocess.call(('sudo', 'pfctl', '-ef', '-'), stdin=ps.stdout)
        ps.wait()
        cast("sudo ifconfig lo0 10.244.7.124 netmask 255.255.255.255 alias")
        
    def unroute_to_localhost(self, ip):
        cast("sudo ifconfig lo0 10.244.7.124 netmask 255.255.255.255 -alias")
        subprocess.call("sudo pfctl -ef /etc/pf.conf".split())

@click.group()
@click.pass_context
def cli(ctx):
    ctx.obj = {}
    ROLLBAR_POST_CLIENT_ITEM = "6fb30e5647474decb3fc8f3175e1dfca"
    rollbar.init(ROLLBAR_POST_CLIENT_ITEM, 'production')
    PLATFORM = call("uname -s").lower() # linux or darwin
    if PLATFORM == "linux":
        ctx.obj['router'] = LinuxRouter()
    elif PLATFORM == "darwin":
        ctx.obj['router'] = DarwinRouter()
    else:
        raise Exception("Unknown platform: %s" % PLATFORM)

def call(cmd):
    return subprocess.check_output(cmd.split()).strip()

def cast(cmd):
    return subprocess.check_call(cmd.split())

def clean_up(router, MY_POD_IP, EPMD_PORT, APP_PORT):
    click.echo("Cleaning up route from %s to 127.0.0.1" % MY_POD_IP)
    router.unroute_to_localhost(MY_POD_IP)
    click.echo("Cleaning up SSH tunnel")
    pid = call("lsof -wni tcp:%(APP_PORT)s -t" % {"APP_PORT": APP_PORT})
    cast("kill -9 %s" % pid)

@cli.command()
@click.argument('app_name')
@click.argument('ssh_ip')
@click.pass_context
def observer(ctx, app_name, ssh_ip):
    """
    launch remote observer to inspect your production nodes
    """
    try:
        click.echo("Fetching pod ip and cookie.")
        ERLANG_COOKIE = call(" ".join(["ssh", "root@%s" % ssh_ip, "--", "cat", "/observer/ERLANG_COOKIE"]))
        MY_POD_IP = call("ssh root@%s cat /observer/MY_POD_IP" % ssh_ip)
        click.echo("Fetching epmd port and app port.")
        output = call("ssh root@%s -- epmd -names" % ssh_ip)
        EPMD_PORT = None
        APP_PORT = None
        for line in output.splitlines():
            match = re.match("^epmd: up and running on port (\d+) with data:$", line)
            if match:
                EPMD_PORT = match.groups()[0]
            match = re.match("^name %s at port (\d+)$" % app_name, line)
            if match:
                APP_PORT = match.groups()[0]
        if EPMD_PORT == None:
            raise Exception("EPMD_PORT not found.")
        if APP_PORT == None:
            raise Exception("APP_PORT not found.")
    except:
        click.echo("Unexpected error:", sys.exc_info()[0])
        rollbar.report_exc_info()
        raise

    try:
        click.echo("Setting up SSH tunnel for ports %s and %s" % (APP_PORT, EPMD_PORT))
        cmd = "".join(["ssh -L %s" % APP_PORT, ":localhost:", "%s -L %s" % (APP_PORT, EPMD_PORT), ":localhost:", "%s root@%s -f -N" % (EPMD_PORT, ssh_ip)])
        cast(cmd)
        click.echo("Routing %s to 127.0.0.1" % MY_POD_IP)
        ctx.obj['router'].route_to_localhost(MY_POD_IP)
        name = uuid.uuid4()
        # cmd = "iex --name %(name)s@%(MY_POD_IP)s --cookie %(ERLANG_COOKIE)s --hidden -e ':observer.start()'" % {"name": name, "MY_POD_IP": MY_POD_IP, "ERLANG_COOKIE": ERLANG_COOKIE}
        cmd = "erl -name %(name)s@%(MY_POD_IP)s -setcookie %(ERLANG_COOKIE)s -hidden -run observer" % {"name": name, "MY_POD_IP": MY_POD_IP, "ERLANG_COOKIE": ERLANG_COOKIE}
        click.echo("Running observer using: %s" % cmd)
        click.echo("In the 'Node' menu, click 'Connect Node'" )
        click.echo("Enter: %(app_name)s@%(MY_POD_IP)s" % {"app_name": app_name, "MY_POD_IP": MY_POD_IP})
        cast(cmd)
    except:
        click.echo("Unexpected error: %s" % sys.exc_info()[0])
        rollbar.report_exc_info()
        raise
    finally:
        clean_up(ctx.obj['router'], MY_POD_IP, EPMD_PORT, APP_PORT)

