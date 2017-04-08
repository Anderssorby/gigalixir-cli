# This Python file uses the following encoding: utf-8
import os
from sure import expect
import subprocess
import gigalixir
import click
from click.testing import CliRunner
import httpretty

@httpretty.activate
def test_create_user():
    httpretty.register_uri(httpretty.POST, 'https://api.stripe.com/v1/tokens', body='{"id":"fake-stripe-token"}', content_type='application/json')
    httpretty.register_uri(httpretty.POST, 'https://api.gigalixir.com/api/users', body='{}', content_type='application/json')
    runner = CliRunner()
    result = runner.invoke(gigalixir.cli, ['create', 'user', '--email=foo@gigalixir.com', '--card_number=4111111111111111', '--card_exp_month=12', '--card_exp_year=34', '--card_cvc=123', '-y'], input="password\n")
    assert result.exit_code == 0
    expect(httpretty.has_request()).to.be.true
    expect(httpretty.httpretty.latest_requests[0].body).to.equal('card%5Bnumber%5D=4111111111111111&card%5Bexp_year%5D=34&card%5Bcvc%5D=123&card%5Bexp_month%5D=12')
    expect(httpretty.httpretty.latest_requests[1].body).to.equal('{"stripe_token": "fake-stripe-token", "password": "password", "email": "foo@gigalixir.com"}')

@httpretty.activate
def test_logout():
    runner = CliRunner()
    # Make sure this test does not modify the user's netrc file.
    with runner.isolated_filesystem():
        os.environ['HOME'] = '.'
        with open('.netrc', 'w') as f:
            f.write("""machine api.gigalixir.com
\tlogin foo@gigalixir.com
\tpassword fake-api-key
machine git.gigalixir.com
\tlogin foo@gigalixir.com
\tpassword fake-api-key
machine github.com
\tlogin foo
\tpassword fake-password
machine localhost
\tlogin foo@gigalixir.com
\tpassword fake-api-key
""")
            os.chmod(".netrc", 0600)
        result = runner.invoke(gigalixir.cli, ['logout'])
        assert result.output == ''
        assert result.exit_code == 0
        with open('.netrc') as f:
            assert f.read() == """machine github.com
\tlogin foo
\tpassword fake-password
"""

@httpretty.activate
def test_login():
    httpretty.register_uri(httpretty.GET, 'https://api.gigalixir.com/api/login', body='{"data":{"key": "fake-api-key"}}', content_type='application/json')
    runner = CliRunner()

    # Make sure this test does not modify the user's netrc file.
    with runner.isolated_filesystem():
        os.environ['HOME'] = '.'
        result = runner.invoke(gigalixir.cli, ['login', '--email=foo@gigalixir.com'], input="password\ny\n")
        assert result.exit_code == 0
        with open('.netrc') as f:
            assert f.read() == """machine api.gigalixir.com
\tlogin foo@gigalixir.com
\tpassword fake-api-key
machine git.gigalixir.com
\tlogin foo@gigalixir.com
\tpassword fake-api-key
machine localhost
\tlogin foo@gigalixir.com
\tpassword fake-api-key
"""
    expect(httpretty.has_request()).to.be.true
    expect(httpretty.last_request().headers.headers).to.contain('Authorization: Basic Zm9vQGdpZ2FsaXhpci5jb206cGFzc3dvcmQ=\r\n')

@httpretty.activate
def test_create_app():
    httpretty.register_uri(httpretty.POST, 'https://api.gigalixir.com/api/apps', body='{}', content_type='application/json', status=201)
    runner = CliRunner()
    with runner.isolated_filesystem():
        subprocess.check_call(['git', 'init'])
        result = runner.invoke(gigalixir.cli, ['create', 'app', 'fake-app-name'])
        remotes = subprocess.check_output(['git', 'remote', '-v'])
        assert remotes == """gigalixir\thttps://git.gigalixir.com/fake-app-name.git/ (fetch)
gigalixir\thttps://git.gigalixir.com/fake-app-name.git/ (push)
"""
        assert result.exit_code == 0
    expect(httpretty.has_request()).to.be.true
    expect(httpretty.last_request().body).to.equal('{"unique_name": "fake-app-name"}')

@httpretty.activate
def test_update_user():
    httpretty.register_uri(httpretty.PATCH, 'https://api.gigalixir.com/api/users', body='{}', content_type='application/json')
    runner = CliRunner()
    result = runner.invoke(gigalixir.cli, ['update', 'user', 'foo@gigalixir.com'], input="current_password\nnew_password\n")
    assert result.exit_code == 0
    expect(httpretty.has_request()).to.be.true
    expect(httpretty.last_request().body).to.equal('{"new_password": "new_password"}')

@httpretty.activate
def test_get_apps():
    httpretty.register_uri(httpretty.GET, 'https://api.gigalixir.com/api/apps', body='{"data":[{"unique_name":"one","size_m":500,"replicas":1},{"unique_name":"two","size_m":500,"replicas":1},{"unique_name":"three","size_m":500,"replicas":1},{"unique_name":"four","size_m":500,"replicas":1},{"unique_name":"five","size_m":500,"replicas":1}]}', content_type='application/json')
    runner = CliRunner()
    result = runner.invoke(gigalixir.cli, ['get', 'apps'])
    assert result.output == """[
  {
    "name": "one", 
    "replicas": 1, 
    "size": 0.5
  }, 
  {
    "name": "two", 
    "replicas": 1, 
    "size": 0.5
  }, 
  {
    "name": "three", 
    "replicas": 1, 
    "size": 0.5
  }, 
  {
    "name": "four", 
    "replicas": 1, 
    "size": 0.5
  }, 
  {
    "name": "five", 
    "replicas": 1, 
    "size": 0.5
  }
]
"""
    assert result.exit_code == 0
    expect(httpretty.has_request()).to.be.true

@httpretty.activate
def test_scale_replicas_only():
    httpretty.register_uri(httpretty.PUT, 'https://api.gigalixir.com/api/apps/fake-app-name/scale', body='{}', content_type='application/json')
    runner = CliRunner()
    result = runner.invoke(gigalixir.cli, ['scale', 'fake-app-name', '--replicas=100'])
    assert result.output == ''
    assert result.exit_code == 0
    expect(httpretty.has_request()).to.be.true
    expect(httpretty.last_request().body).to.equal('{"replicas": 100}')

@httpretty.activate
def test_scale():
    httpretty.register_uri(httpretty.PUT, 'https://api.gigalixir.com/api/apps/fake-app-name/scale', body='{}', content_type='application/json')
    runner = CliRunner()
    result = runner.invoke(gigalixir.cli, ['scale', 'fake-app-name', '--replicas=100', '--size=0.5'])
    assert result.output == ''
    assert result.exit_code == 0
    expect(httpretty.has_request()).to.be.true
    expect(httpretty.last_request().body).to.equal('{"size": 500, "replicas": 100}')

@httpretty.activate
def test_restart():
    httpretty.register_uri(httpretty.PUT, 'https://api.gigalixir.com/api/apps/fake-app-name/restart', body='{}', content_type='application/json')
    runner = CliRunner()
    result = runner.invoke(gigalixir.cli, ['restart', 'fake-app-name'])
    assert result.output == ''
    assert result.exit_code == 0
    expect(httpretty.has_request()).to.be.true

@httpretty.activate
def test_run():
    httpretty.register_uri(httpretty.PUT, 'https://api.gigalixir.com/api/apps/fake-app-name/run', body='{}', content_type='application/json')
    runner = CliRunner()
    result = runner.invoke(gigalixir.cli, ['run', 'fake-app-name', 'Elixir.Tasks', 'migrate'])
    assert result.output == ''
    assert result.exit_code == 0
    expect(httpretty.has_request()).to.be.true
    expect(httpretty.last_request().body).to.equal('{"function": "migrate", "module": "Elixir.Tasks"}')

@httpretty.activate
def test_get_configs():
    httpretty.register_uri(httpretty.GET, 'https://api.gigalixir.com/api/apps/fake-app-name/configs', body='{"data":{"DATABASE_URL":"ecto://user:pass@host:5432/db"}}', content_type='application/json')
    runner = CliRunner()
    result = runner.invoke(gigalixir.cli, ['get', 'configs', 'fake-app-name'])
    assert result.output == """{
  "DATABASE_URL": "ecto://user:pass@host:5432/db"
}
"""
    assert result.exit_code == 0
    expect(httpretty.has_request()).to.be.true

@httpretty.activate
def test_create_config():
    httpretty.register_uri(httpretty.POST, 'https://api.gigalixir.com/api/apps/fake-app-name/configs', body='{}', content_type='application/json', status=201)
    runner = CliRunner()
    result = runner.invoke(gigalixir.cli, ['create', 'config', 'fake-app-name', 'FOO', 'bar'])
    assert result.exit_code == 0
    expect(httpretty.has_request()).to.be.true
    expect(httpretty.last_request().body).to.equal('{"value": "bar", "key": "FOO"}')

@httpretty.activate
def test_delete_config():
    httpretty.register_uri(httpretty.DELETE, 'https://api.gigalixir.com/api/apps/fake-app-name/configs', body='{}', content_type='application/json')
    runner = CliRunner()
    result = runner.invoke(gigalixir.cli, ['delete', 'config', 'fake-app-name', 'FOO'])
    assert result.exit_code == 0
    expect(httpretty.has_request()).to.be.true
    expect(httpretty.last_request().body).to.equal('{"key": "FOO"}')

@httpretty.activate
def test_get_permissions():
    httpretty.register_uri(httpretty.GET, 'https://api.gigalixir.com/api/apps/fake-app-name/permissions', body='{"data":["foo@gigalixir.com"]}', content_type='application/json')
    runner = CliRunner()
    result = runner.invoke(gigalixir.cli, ['get', 'permissions', 'fake-app-name'])
    assert result.exit_code == 0
    expect(httpretty.has_request()).to.be.true

@httpretty.activate
def test_create_permission():
    httpretty.register_uri(httpretty.POST, 'https://api.gigalixir.com/api/apps/fake-app-name/permissions', body='{}', content_type='application/json', status=201)
    runner = CliRunner()
    result = runner.invoke(gigalixir.cli, ['create', 'permission', 'fake-app-name', 'foo@gigalixir.com'])
    assert result.exit_code == 0
    expect(httpretty.has_request()).to.be.true
    expect(httpretty.last_request().body).to.equal('{"email": "foo@gigalixir.com"}')

@httpretty.activate
def test_delete_permission():
    httpretty.register_uri(httpretty.DELETE, 'https://api.gigalixir.com/api/apps/fake-app-name/permissions', body='{}', content_type='application/json')
    runner = CliRunner()
    result = runner.invoke(gigalixir.cli, ['delete', 'permission', 'fake-app-name', 'foo@gigalixir.com'])
    assert result.exit_code == 0
    expect(httpretty.has_request()).to.be.true
    expect(httpretty.last_request().body).to.equal('{"email": "foo@gigalixir.com"}')

@httpretty.activate
def test_create_api_key():
    httpretty.register_uri(httpretty.POST, 'https://api.gigalixir.com/api/api_keys', body='{"data":{"key":"another-fake-api-key","expires_at":"2017-04-28T16:47:09"}}', content_type='application/json', status=201)
    runner = CliRunner()
    # Make sure this test does not modify the user's netrc file.
    with runner.isolated_filesystem():
        os.environ['HOME'] = '.'
        result = runner.invoke(gigalixir.cli, ['update', 'api_key', 'foo@gigalixir.com'], input="password\ny\n")
        assert result.exit_code == 0
        with open('.netrc') as f:
            assert f.read() == """machine api.gigalixir.com
\tlogin foo@gigalixir.com
\tpassword another-fake-api-key
machine git.gigalixir.com
\tlogin foo@gigalixir.com
\tpassword another-fake-api-key
machine localhost
\tlogin foo@gigalixir.com
\tpassword another-fake-api-key
"""
    expect(httpretty.has_request()).to.be.true
    expect(httpretty.last_request().headers.headers).to.contain('Authorization: Basic Zm9vQGdpZ2FsaXhpci5jb206cGFzc3dvcmQ=\r\n')

@httpretty.activate
def test_get_releases():
    httpretty.register_uri(httpretty.GET, 'https://api.gigalixir.com/api/apps/fake-app-name/releases', body='{"data":[{"slug_url":"another-fake-slug-url","sha":"another-fake-sha","rollback_id":"fake-rollback-id3","customer_app_name":"gigalixir_getting_started","created_at":"2017-03-29T17:28:29.000+00:00"},{"slug_url":"fake-slug-url","sha":"fake-sha","rollback_id":"fake-rollback-id2","customer_app_name":"gigalixir_getting_started","created_at":"2017-03-29T17:28:28.000+00:00"}]}', content_type='application/json')
    runner = CliRunner()
    result = runner.invoke(gigalixir.cli, ['get', 'releases', 'fake-app-name'])
    assert result.exit_code == 0
    expect(httpretty.has_request()).to.be.true
    assert result.output == """[
  {
    "created_at": "2017-03-29T17:28:29.000+00:00", 
    "customer_app_name": "gigalixir_getting_started", 
    "rollback_id": "fake-rollback-id3", 
    "sha": "another-fake-sha", 
    "slug_url": "another-fake-slug-url"
  }, 
  {
    "created_at": "2017-03-29T17:28:28.000+00:00", 
    "customer_app_name": "gigalixir_getting_started", 
    "rollback_id": "fake-rollback-id2", 
    "sha": "fake-sha", 
    "slug_url": "fake-slug-url"
  }
]
"""

@httpretty.activate
def test_rollback_without_eligible_release():
    httpretty.register_uri(httpretty.GET, 'https://api.gigalixir.com/api/apps/fake-app-name/releases', body='{"data":[{"slug_url":"another-fake-slug-url","sha":"another-fake-sha","rollback_id":"fake-rollback-id3","customer_app_name":"gigalixir_getting_started","created_at":"2017-03-29T17:28:29.000+00:00"}]}', content_type='application/json')
    httpretty.register_uri(httpretty.POST, 'https://api.gigalixir.com/api/apps/fake-app-name/releases/fake-rollback-id2/rollback', body='', content_type='application/json')
    runner = CliRunner()
    result = runner.invoke(gigalixir.cli, ['rollback', 'fake-app-name'])
    assert result.exit_code == 1
    expect(httpretty.has_request()).to.be.true
    expect(httpretty.has_request()).to.be.true
    expect(len(httpretty.httpretty.latest_requests)).to.equal(1)

@httpretty.activate
def test_rollback_without_rollback_id():
    httpretty.register_uri(httpretty.GET, 'https://api.gigalixir.com/api/apps/fake-app-name/releases', body='{"data":[{"slug_url":"another-fake-slug-url","sha":"another-fake-sha","rollback_id":"fake-rollback-id3","customer_app_name":"gigalixir_getting_started","created_at":"2017-03-29T17:28:29.000+00:00"},{"slug_url":"fake-slug-url","sha":"fake-sha","rollback_id":"fake-rollback-id2","customer_app_name":"gigalixir_getting_started","created_at":"2017-03-29T17:28:28.000+00:00"}]}', content_type='application/json')
    httpretty.register_uri(httpretty.POST, 'https://api.gigalixir.com/api/apps/fake-app-name/releases/fake-rollback-id2/rollback', body='{"data":{"slug_url":"another-fake-slug-url","sha":"another-fake-sha","rollback_id":"52e5dc7b-30d2-4325-afe3-087edeb5f3c2","customer_app_name":"gigalixir_getting_started","created_at":"2017-03-29T17:38:35.000+00:00"}}', content_type='application/json')
    runner = CliRunner()
    result = runner.invoke(gigalixir.cli, ['rollback', 'fake-app-name'])
    assert result.output == ''
    assert result.exit_code == 0
    expect(httpretty.has_request()).to.be.true

@httpretty.activate
def test_rollback():
    httpretty.register_uri(httpretty.POST, 'https://api.gigalixir.com/api/apps/fake-app-name/releases/fake-rollback-id/rollback', body='{"data":{"slug_url":"another-fake-slug-url","sha":"another-fake-sha","rollback_id":"52e5dc7b-30d2-4325-afe3-087edeb5f3c2","customer_app_name":"gigalixir_getting_started","created_at":"2017-03-29T17:38:35.000+00:00"}}', content_type='application/json')
    runner = CliRunner()
    result = runner.invoke(gigalixir.cli, ['rollback', 'fake-app-name', '-r', 'fake-rollback-id'])
    assert result.output == ''
    assert result.exit_code == 0
    expect(httpretty.has_request()).to.be.true

@httpretty.activate
def test_get_ssh_keys():
    httpretty.register_uri(httpretty.GET, 'https://api.gigalixir.com/api/ssh_keys', body='{"data":[{"key":"fake-ssh-key","id":1}]}', content_type='application/json')
    runner = CliRunner()
    result = runner.invoke(gigalixir.cli, ['get', 'ssh_keys'])
    assert result.output == """[
  {
    "id": 1, 
    "key": "fake-ssh-key"
  }
]
"""
    assert result.exit_code == 0
    expect(httpretty.has_request()).to.be.true

@httpretty.activate
def test_create_ssh_key():
    httpretty.register_uri(httpretty.POST, 'https://api.gigalixir.com/api/ssh_keys', body='', content_type='application/json', status=201)
    runner = CliRunner()
    result = runner.invoke(gigalixir.cli, ['create', 'ssh_key', 'fake-ssh-key'])
    assert result.output == ''
    assert result.exit_code == 0
    expect(httpretty.has_request()).to.be.true
    expect(httpretty.last_request().body).to.equal('{"ssh_key": "fake-ssh-key"}')

@httpretty.activate
def test_delete_ssh_key():
    httpretty.register_uri(httpretty.DELETE, 'https://api.gigalixir.com/api/ssh_keys/3', body='', content_type='application/json')
    runner = CliRunner()
    result = runner.invoke(gigalixir.cli, ['delete', 'ssh_key', '3'])
    assert result.output == ''
    assert result.exit_code == 0
    expect(httpretty.has_request()).to.be.true

@httpretty.activate
def test_get_payment_method():
    httpretty.register_uri(httpretty.GET, 'https://api.gigalixir.com/api/payment_methods', body='{"data":{"last4":4242,"exp_year":2018,"exp_month":12,"brand":"Visa"}}', content_type='application/json')
    runner = CliRunner()
    result = runner.invoke(gigalixir.cli, ['get', 'payment_method'])
    assert result.output == """{
  "brand": "Visa", 
  "exp_month": 12, 
  "exp_year": 2018, 
  "last4": 4242
}
"""
    assert result.exit_code == 0
    expect(httpretty.has_request()).to.be.true

@httpretty.activate
def test_update_payment_method():
    httpretty.register_uri(httpretty.PUT, 'https://api.gigalixir.com/api/payment_methods', body='{}', content_type='application/json', status=201)
    runner = CliRunner()
    result = runner.invoke(gigalixir.cli, ['update', 'payment_method', 'fake-stripe-token'])
    assert result.output == ''
    assert result.exit_code == 0
    expect(httpretty.has_request()).to.be.true
    expect(httpretty.last_request().body).to.equal('{"stripe_token": "fake-stripe-token"}')

@httpretty.activate
def test_logs():
    def log_response():
        from time import sleep
        for i in range(3):
            yield(u"%i 18:14:58.885 request_id=406arqcek0jjs7uo29o34o55sr841jec [info] Sent 200 in 197µs\n" % i)

    httpretty.register_uri(httpretty.GET, 'https://api.gigalixir.com/api/apps/fake-app-name/logs', body=log_response(), streaming=True)
    runner = CliRunner()
    result = runner.invoke(gigalixir.cli, ['get', 'logs', 'fake-app-name'])
    assert result.output == u"\n".join([
        u"0 18:14:58.885 request_id=406arqcek0jjs7uo29o34o55sr841jec [info] Sent 200 in 197µs",
        u"1 18:14:58.885 request_id=406arqcek0jjs7uo29o34o55sr841jec [info] Sent 200 in 197µs",
        u"2 18:14:58.885 request_id=406arqcek0jjs7uo29o34o55sr841jec [info] Sent 200 in 197µs",
        u""
    ])
    assert result.exit_code == 0
    expect(httpretty.has_request()).to.be.true

@httpretty.activate
def test_delete_domain():
    httpretty.register_uri(httpretty.DELETE, 'https://api.gigalixir.com/api/apps/fake-app-name/domains', body='{}', content_type='application/json')
    runner = CliRunner()
    result = runner.invoke(gigalixir.cli, ['delete', 'domain', 'fake-app-name', 'www.example.com'])
    assert result.output == ''
    assert result.exit_code == 0
    expect(httpretty.has_request()).to.be.true
    expect(httpretty.last_request().body).to.equal('{"fqdn": "www.example.com"}')

@httpretty.activate
def test_get_domains():
    httpretty.register_uri(httpretty.GET, 'https://api.gigalixir.com/api/apps/fake-app-name/domains', body='{"data":["www.example.com"]}', content_type='application/json')
    runner = CliRunner()
    result = runner.invoke(gigalixir.cli, ['get', 'domains', 'fake-app-name'])
    assert result.output == """[
  "www.example.com"
]
"""
    assert result.exit_code == 0
    expect(httpretty.has_request()).to.be.true

@httpretty.activate
def test_create_domain():
    httpretty.register_uri(httpretty.POST, 'https://api.gigalixir.com/api/apps/fake-app-name/domains', body='{}', content_type='application/json', status=201)
    runner = CliRunner()
    result = runner.invoke(gigalixir.cli, ['create', 'domain', 'fake-app-name', 'www.example.com'])
    assert result.output == ''
    assert result.exit_code == 0
    expect(httpretty.has_request()).to.be.true
    expect(httpretty.last_request().body).to.equal('{"fqdn": "www.example.com"}')

@httpretty.activate
def test_resend_confirmation_token():
    httpretty.register_uri(httpretty.PUT, 'https://api.gigalixir.com/api/users/reconfirm_email', body='{}', content_type='application/json', status=200)
    runner = CliRunner()
    result = runner.invoke(gigalixir.cli, ['get', 'email_confirmation_token', 'foo@gigalixir.com'])
    assert result.output == ''
    assert result.exit_code == 0
    expect(httpretty.has_request()).to.be.true
    expect(httpretty.last_request().body).to.equal('{"email": "foo@gigalixir.com"}')

@httpretty.activate
def test_get_reset_password_token():
    httpretty.register_uri(httpretty.PUT, 'https://api.gigalixir.com/api/users/reset_password', body='{}', content_type='application/json', status=200)
    runner = CliRunner()
    result = runner.invoke(gigalixir.cli, ['get', 'reset_password_token', 'foo@gigalixir.com'])
    assert result.output == ''
    assert result.exit_code == 0
    expect(httpretty.has_request()).to.be.true
    expect(httpretty.last_request().body).to.equal('{"email": "foo@gigalixir.com"}')

@httpretty.activate
def test_reset_password():
    httpretty.register_uri(httpretty.POST, 'https://api.gigalixir.com/api/users/reset_password', body='{}', content_type='application/json', status=200)
    runner = CliRunner()
    result = runner.invoke(gigalixir.cli, ['reset', 'password', '--token=fake-token'], input="password\n")
    assert result.exit_code == 0
    expect(httpretty.has_request()).to.be.true
    expect(httpretty.last_request().body).to.equal('{"token": "fake-token", "password": "password"}')
