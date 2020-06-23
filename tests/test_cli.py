from pathlib import Path
import re
import pytest
from notesdir import cli


def nd_setup(fs):
    fs.cwd = '/notes/cwd'
    Path('~').expanduser().mkdir(parents=True)
    Path('~/.notesdir.toml').expanduser().write_text("""
        root = "/notes"
    """)


def test_help(capsys):
    """Writes usage info to the doc/ folder."""
    doc = Path('doc')
    with pytest.raises(SystemExit):
        cli.main(['-h'])
    cap = capsys.readouterr()
    doc.joinpath('usage.txt').write_text(
        re.sub(r'\S*pytest\S*', 'notesdir', cap.out))
    cmds = re.search('\\{(.+)\\}', cap.out).group(1)
    for cmd in cmds.split(','):
        with pytest.raises(SystemExit):
            cli.main([cmd, '-h'])
        cap = capsys.readouterr()
        doc.joinpath(f'usage-{cmd}.txt').write_text(
            re.sub(r'\S*pytest\S*', 'notesdir', cap.out))


def test_mv_file(fs, capsys):
    nd_setup(fs)
    fs.create_file('/notes/cwd/subdir/old.md')
    fs.create_file('/notes/dir/referrer.md', contents='I have a [link](../cwd/subdir/old.md).')
    assert cli.main(['mv', 'subdir/old.md', '../dir/new.md']) == 0
    assert not Path('/notes/cwd/subdir/old.md').exists()
    assert Path('/notes/dir/new.md').exists()
    assert Path('/notes/dir/referrer.md').read_text() == 'I have a [link](new.md).'
    out, err = capsys.readouterr()
    assert not out


def test_mv_file_to_dir(fs, capsys):
    nd_setup(fs)
    fs.create_file('/notes/cwd/subdir/old.md')
    fs.create_file('/notes/dir/referrer.md', contents='I have a [link](../cwd/subdir/old.md).')
    assert cli.main(['mv', 'subdir/old.md', '../dir']) == 0
    assert not Path('/notes/cwd/subdir/old.md').exists()
    assert Path('/notes/dir/old.md').exists()
    assert Path('/notes/dir/referrer.md').read_text() == 'I have a [link](old.md).'
    out, err = capsys.readouterr()
    assert not out


def test_mv_file_conflict(fs, capsys):
    nd_setup(fs)
    fs.create_file('/notes/cwd/referrer.md', contents='I have a [link](foo.md).')
    fs.create_file('/notes/cwd/foo.md', contents='foo')
    fs.create_file('/notes/dir/bar.md', contents='bar')
    fs.create_file('/notes/dir/2-bar.md', contents='baz')
    assert cli.main(['mv', 'foo.md', '../dir/bar.md']) == 0
    assert not Path('/notes/cwd/foo.md').exists()
    assert Path('/notes/dir/bar.md').read_text() == 'bar'
    assert Path('/notes/dir/2-bar.md').read_text() == 'baz'
    assert Path('/notes/dir/3-bar.md').read_text() == 'foo'
    assert Path('/notes/cwd/referrer.md').read_text() == 'I have a [link](../dir/3-bar.md).'
    out, err = capsys.readouterr()
    assert 'Moved to: ../dir/3-bar.md' in out


def test_mv_file_to_dir_conflict(fs, capsys):
    nd_setup(fs)
    fs.create_file('/notes/cwd/referrer.md', contents='I have a [link](foo.md).')
    fs.create_file('/notes/cwd/foo.md', contents='foo')
    fs.create_file('/notes/dir/foo.md', contents='bar')
    assert cli.main(['mv', 'foo.md', '../dir']) == 0
    assert not Path('/notes/cwd/foo.md').exists()
    assert Path('/notes/dir/foo.md').read_text() == 'bar'
    assert Path('/notes/dir/2-foo.md').read_text() == 'foo'
    assert Path('/notes/cwd/referrer.md').read_text() == 'I have a [link](../dir/2-foo.md).'
    out, err = capsys.readouterr()
    assert 'Moved to: ../dir/2-foo.md' in out
