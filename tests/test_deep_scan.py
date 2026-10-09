import json
from pathlib import Path

import pytest

from src.deep_scan import ResearchClient, architecture, inventory, research, write_bundle
from src.full_scan import render, scan


class FixtureClient:
    def __init__(self):
        self.used = 0

    def get(self, url, payload=None):
        self.used += 1
        if url.endswith('/json'):
            return {'info': {'version': '2.0', 'requires_python': '>=3.10'}}
        return {'vulns': [{'id': 'TEST-ADVISORY'}]}


def test_approval_gate_never_calls_network(tmp_path):
    (tmp_path / 'requirements.txt').write_text('sample==1.0\n')
    client = FixtureClient()
    result = research(tmp_path, client=client)
    assert client.used == 0
    assert result['approval_required']
    assert result['status'] == 'LOCAL_ONLY'


def test_declared_range_is_not_reported_as_installed_version(tmp_path):
    (tmp_path / 'requirements.txt').write_text('sample>=1.0\npinned==1.0\n')
    result = research(tmp_path, approved=True, client=FixtureClient())
    ranged, pinned = result['dependencies']
    assert ranged['version'] is None
    assert ranged['vulnerability_status'] == 'UNKNOWN'
    assert pinned['advisories'] == ['TEST-ADVISORY']
    assert result['usage']['provider_cost'] is None


def test_diagram_and_duplicates_are_grounded_in_ast(tmp_path):
    (tmp_path / 'a.py').write_text('import b\ndef f():\n    x = 1\n    y = 2\n    return x + y\n')
    (tmp_path / 'b.py').write_text('def g():\n    x = 1\n    y = 2\n    return x + y\n')
    result = architecture(tmp_path)
    assert ('a', 'b') in result['edges']
    assert result['duplicate_candidates'] == [['a.py:2', 'b.py:1']]
    assert '#ffffff' in result['mermaid']
    assert 'n0 --> n1' in result['mermaid']


def test_reports_do_not_leak_secret_literals(tmp_path):
    (tmp_path / 'sample.py').write_text('api_key = "sensitive-test-value"\n')
    assert 'sensitive-test-value' not in render(scan(tmp_path), root=tmp_path, mode='strict')
    directory = write_bundle(research(tmp_path))
    assert 'sensitive-test-value' not in (directory / 'evidence/report.json').read_text()
    assert (directory / 'architecture/imports.mmd').exists()
    assert json.loads((directory / 'evidence/report.json').read_text())['schema'] == '1.0'


def test_request_cap_and_allowlist():
    client = ResearchClient(1)
    with pytest.raises(ValueError):
        client.get('http://localhost/private')
    client.used = 1
    with pytest.raises(RuntimeError):
        client.get('https://pypi.org/pypi/example/json')


def test_npm_lock_inventory(tmp_path):
    (tmp_path / 'package-lock.json').write_text(json.dumps({'packages': {'node_modules/@scope/pkg': {'version': '1.0.0'}}}))
    assert inventory(tmp_path)[0]['name'] == '@scope/pkg'


def test_source_failure_is_unknown_not_clean(tmp_path):
    class Unavailable(FixtureClient):
        def get(self, url, payload=None):
            raise OSError('offline')
    (tmp_path / 'requirements.txt').write_text('sample==1.0\n')
    result = research(tmp_path, approved=True, client=Unavailable())
    assert result['status'] == 'PARTIAL'
    assert result['dependencies'][0]['vulnerability_status'] == 'UNKNOWN'
    assert result['boundaries']


def test_html_escapes_source_and_bundle_contains_svg(tmp_path):
    from src.deep_scan import html_report
    report = research(tmp_path)
    report['root'] = '<script>alert(1)</script>'
    assert '<script>' not in html_report(report)
    report['root'] = str(tmp_path)
    directory = write_bundle(report)
    assert '<svg' in (directory / 'optional/report.html').read_text()
    assert 'fill="white"' in (directory / 'architecture/overview.svg').read_text()
    assert (directory / 'README.md').exists()
    assert not (directory / 'report.html').exists()


def test_cli_json_is_parseable_without_trailing_paths(tmp_path, monkeypatch, capsys):
    import sys
    from src.cli.main import main
    monkeypatch.setattr(sys, 'argv', ['agentcore', 'deep-scan', '--repo', str(tmp_path), '--json'])
    main()
    captured = capsys.readouterr()
    assert json.loads(captured.out)['status'] == 'LOCAL_ONLY'
    assert 'Reports saved' in captured.err


def test_upstream_documents_are_pinned_and_fingerprinted():
    import base64
    from src.deep_scan import upstream_evidence
    sha = 'a' * 40
    urls = []
    def collect(url):
        urls.append(url)
        if '/contents/' in url:
            return {'encoding': 'base64', 'content': base64.b64encode(b'# Project\n').decode()}
        if '/git/trees/' in url:
            return {'tree': [{'type': 'blob', 'path': 'README.md', 'size': 10}, {'type': 'blob', 'path': 'src/main.py', 'size': 20}]}
        if '/commits/' in url:
            return {'sha': sha}
        return {'default_branch': 'main', 'license': {'spdx_id': 'MIT'}}
    result = upstream_evidence('owner/repo', collect)
    assert result['commit'] == sha
    assert result['documents'][0]['sha256']
    assert urls[-1].endswith('?ref=' + sha)
    assert result['source_files'] == ['src/main.py']


def test_stdlib_os_is_separate_from_dependency_candidates(tmp_path):
    (tmp_path / 'main.py').write_text('import os\nimport third_party\n')
    graph = architecture(tmp_path)
    assert graph['stdlib_imports'] == ['os']
    assert graph['unresolved_imports'] == ['third_party']


def test_rendered_svg_is_valid_xml(tmp_path):
    from xml.etree import ElementTree
    from src.deep_scan import architecture_svg
    (tmp_path / 'a.py').write_text('import b\n')
    (tmp_path / 'b.py').write_text('pass\n')
    tree = ElementTree.fromstring(architecture_svg(architecture(tmp_path)))
    assert tree.tag.endswith('svg')
