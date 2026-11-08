# 사람 라벨 시트

Judge와 같은 루브릭(research/gold_metric_selection.md의 "항목 상세")으로 판정해 `data/gold/human_labels.jsonl`의 빈칸(null)을 채운다. 인용과 요점은 true/false, 품질 항목은 "pass", "fail", "na"다.

## 1. `e4c89614-15fd-553e-8798-f84f234c3f55` (factual, en)

**질문**: Which environment variable can I set to change where uv installs managed Python versions?

**답**:

```text
You can set the `UV_PYTHON_INSTALL_DIR` environment variable to override the installation directory for uv-managed Python versions [1]. By default, those versions are stored in a `python/` subdirectory of the persistent data directory, e.g., `~/.local/share/uv/python` [1].
```

**인용 판정 대상**(문장, 가리키는 근거 번호):

0. [1] You can set the `UV_PYTHON_INSTALL_DIR` environment variable to override the installation directory for uv-managed Python versions [1].
1. [1] By default, those versions are stored in a `python/` subdirectory of the persistent data directory, e.g., `~/.local/share/uv/python` [1].

**핵심 요점**:

0. Names `UV_PYTHON_INSTALL_DIR`.
1. Identifies it as controlling the Python installation directory.

**금지 내용**:

0. Claims `UV_PYTHON_BIN_DIR` changes the managed Python installation directory.

<details><summary>근거 문서</summary>

**[1] reference/storage.md**

```text
### Python versions

uv can install managed [Python versions](../concepts/python-versions.md), e.g., with
`uv python install`.

By default, Python versions managed by uv are stored in a `python/` subdirectory of the
[persistent data directory](#persistent-data-directory), e.g., `~/.local/share/uv/python`.

Use `uv python dir` to show the Python installation directory.

Use the `UV_PYTHON_INSTALL_DIR` environment variable to override the installation directory.

!!! note

    Changing where Python is installed will not be automatically reflected in existing virtual environments; they will keep referring to the old location, and will need to be updated manually (e.g. by re-creating them).

### Python executables

uv installs executables for [Python versions](#python-versions), e.g., `python3.13`.

By default, Python executables are stored in the [executable directory](#executable-directory).

Use `uv python dir --bin` to show the Python executable directory.

Use the `UV_PYTHON_BIN_DIR` environment variable to override the Python executable directory.

### Tools

uv can install Python packages as [command-line tools](../concepts/tools.md) using
`uv tool install`.

By default, tools are installed in a `tools/` subdirectory of the
[persistent data directory](#persistent-data-directory), e.g., `~/.local/share/uv/tools`.

Use `uv tool dir` to show the tool installation directory.

Use the `UV_TOOL_DIR` environment variable to configure the installation directory.

### Tool executables

uv installs executables for installed [tools](#tools), e.g., `ruff`.

By default, tool executables are stored in the [executable directory](#executable-directory).

Use `uv tool dir --bin` to show the tool executable directory.

Use the `UV_TOOL_BIN_DIR` environment variable to configure the tool executable directory.

### The uv executable

When using uv's [standalone installer](./installer.md) to install uv, the `uv` and `uvx` executables
are installed into the [executable directory](#executable-directory).

Use the `UV_INSTALL_DIR` environment variable to configure uv's installation directory.

### Configuration files

uv's behavior can be configured through TOML files.

Configuration files are discovered in the [configuration directories](#configuration-directories).

For more details, see the [configuration files documentation](../concepts/configuration-files.md).
```

**[2] guides/install-python.md**

```text
# Installing Python

If Python is already installed on your system, uv will
[detect and use](#using-existing-python-versions) it without configuration. However, uv can also
install and manage Python versions. uv [automatically installs](#automatic-python-downloads) missing
Python versions as needed — you don't need to install Python to get started.

## Getting started

To install the latest Python version:

```console
$ uv python install
```

!!! note

    Python does not publish official distributable binaries. As such, uv uses distributions from the Astral [`python-build-standalone`](https://github.com/astral-sh/python-build-standalone) project. See the [Python distributions](../concepts/python-versions.md#managed-python-distributions) documentation for more details.

Once Python is installed, it will be used by `uv` commands automatically. uv also adds the installed
version to your `PATH`:

```console
$ python3.15
```

uv only installs a _versioned_ executable by default. To install `python` and `python3` executables,
include the experimental `--default` option:

```console
$ uv python install --default
```

!!! tip

    See the documentation on [installing Python executables](../concepts/python-versions.md#installing-python-executables)
    for more details.

## Installing a specific version

To install a specific Python version:

```console
$ uv python install 3.12
```

To install multiple Python versions:

```console
$ uv python install 3.11 3.12
```

To install an alternative Python implementation, e.g., PyPy:

```console
$ uv python install pypy@3.10
```

See the [`python install`](../concepts/python-versions.md#installing-a-python-version) documentation
for more details.

## Reinstalling Python

To reinstall uv-managed Python versions, use `--reinstall`, e.g.:

```console
$ uv python install --reinstall
```

This will reinstall all previously installed Python versions. Improvements are constantly being
added to the Python distributions, so reinstalling may resolve bugs even if the Python version does
not change.
```

**[3] index.md**

```text
## Python versions

uv installs Python and allows quickly switching between versions.

Install multiple Python versions:

```console
$ uv python install 3.10 3.11 3.12
Searching for Python versions matching: Python 3.10
Searching for Python versions matching: Python 3.11
Searching for Python versions matching: Python 3.12
Installed 3 versions in 3.42s
 + cpython-3.10.14-macos-aarch64-none
 + cpython-3.11.9-macos-aarch64-none
 + cpython-3.12.4-macos-aarch64-none
```

Download Python versions as needed:

```console
$ uv venv --python 3.12.0
Using CPython 3.12.0
Creating virtual environment at: .venv
Activate with: source .venv/bin/activate

$ uv run --python pypy@3.8 -- python
Python 3.8.16 (a9dbdca6fc3286b0addd2240f11d97d8e8de187a, Dec 29 2022, 11:45:30)
[PyPy 7.3.11 with GCC Apple LLVM 13.1.6 (clang-1316.0.21.2.5)] on darwin
Type "help", "copyright", "credits" or "license" for more information.
>>>>
```

Use a specific Python version in the current directory:

```console
$ uv python pin 3.11
Pinned `.python-version` to `3.11`
```

See the [installing Python guide](./guides/install-python.md) to get started.
```

**[4] pip/environments.md**

```text
# Using Python environments

Each Python installation has an environment that is active when Python is used. Packages can be
installed into an environment to make their modules available from your Python scripts. Generally,
it is considered best practice not to modify a Python installation's environment. This is especially
important for Python installations that come with the operating system which often manage the
packages themselves. A virtual environment is a lightweight way to isolate packages from a Python
installation's environment. Unlike `pip`, uv requires using a virtual environment by default.

## Creating a virtual environment

uv supports creating virtual environments, e.g., to create a virtual environment at `.venv`:

```console
$ uv venv
```

A specific name or path can be specified, e.g., to create a virtual environment at `my-name`:

```console
$ uv venv my-name
```

A Python version can be requested, e.g., to create a virtual environment with Python 3.11:

```console
$ uv venv --python 3.11
```

Note this requires the requested Python version to be available on the system. However, if
unavailable, uv will download Python for you. See the
[Python version](../concepts/python-versions.md) documentation for more details.

## Using a virtual environment

When using the default virtual environment name, uv will automatically find and use the virtual
environment during subsequent invocations.

```console
$ uv venv

$ # Install a package in the new virtual environment
$ uv pip install ruff
```

The virtual environment can be "activated" to make its packages available:

=== "macOS and Linux"

    ```console
    $ source .venv/bin/activate
    ```

=== "Windows"

    ```pwsh-session
    PS> .venv\Scripts\activate
    ```

!!! note

    The default activation script on Unix is for POSIX compliant shells like `sh`, `bash`, or `zsh`.
    There are additional activation scripts for common alternative shells.

    === "fish"

        ```console
        $ source .venv/bin/activate.fish
        ```

    === "csh / tcsh"

        ```console
        $ source .venv/bin/activate.csh
        ```

    === "Nushell"

        ```console
        $ use .venv\Scripts\activate.nu
        ```
```

**[5] pip/environments.md**

```text
## Using arbitrary Python environments

Since uv has no dependency on Python, it can install into virtual environments other than its own.
For example, setting `VIRTUAL_ENV=/path/to/venv` will cause uv to install into `/path/to/venv`,
regardless of where uv is installed. Note that if `VIRTUAL_ENV` is set to a directory that is
**not** a [PEP 405 compliant](https://peps.python.org/pep-0405/#specification) virtual environment,
it will be ignored.

uv can also install into arbitrary, even non-virtual environments, with the `--python` option. For
example, `uv pip install --python /path/to/python` will install into the environment linked to the
`/path/to/python` interpreter regardless of whether or not it is a virtual environment. The
`--python` option also accepts a path to the root directory of a virtual environment.

For convenience, `uv pip install --system` will install into the system Python environment. Using
`--system` is roughly equivalent to `uv pip install --python $(which python)`, but note that
executables that are linked to virtual environments will be skipped. Although we generally recommend
using virtual environments for dependency management, `--system` is appropriate in continuous
integration and containerized environments.

The `--system` flag is also used to opt in to mutating system environments. For example, the
`--python` argument can be used to request a Python version (e.g., `--python 3.12`), and uv will
search for an interpreter that meets the request. If uv finds a system interpreter (e.g.,
`/usr/lib/python3.12`), then the `--system` flag is required to allow modification of this
non-virtual Python environment. Without the `--system` flag, uv will ignore any interpreters that
are not in virtual environments. Conversely, when the `--system` flag is provided, uv will ignore
any interpreters that _are_ in virtual environments.
```

</details>

## 2. `155cb1f6-2b9c-550e-8f46-cbe41337d0c7` (factual, ko)

**질문**: uv가 관리하는 Python 버전의 설치 위치를 바꾸려면 어떤 환경 변수를 설정하면 되나요?

**답**:

```text
uv가 관리하는 Python 버전의 설치 위치는 `UV_PYTHON_INSTALL_DIR` 환경 변수로 바꿀 수 있습니다 [1]. 기본 위치는 영구 데이터 디렉터리의 `python/` 하위 디렉터리(예: `~/.local/share/uv/python`)입니다 [1].

설치 위치를 바꾸면 기존 가상 환경은 자동으로 반영되지 않고 예전 위치를 계속 참조하므로, 수동으로 업데이트하거나 다시 생성해야 합니다 [1]. 현재 설치 디렉터리는 `uv python dir` 명령으로 확인할 수 있습니다 [1].
```

**인용 판정 대상**(문장, 가리키는 근거 번호):

0. [1] uv가 관리하는 Python 버전의 설치 위치는 `UV_PYTHON_INSTALL_DIR` 환경 변수로 바꿀 수 있습니다 [1].
1. [1] 기본 위치는 영구 데이터 디렉터리의 `python/` 하위 디렉터리(예: `~/.local/share/uv/python`)입니다 [1].
2. [1] 설치 위치를 바꾸면 기존 가상 환경은 자동으로 반영되지 않고 예전 위치를 계속 참조하므로, 수동으로 업데이트하거나 다시 생성해야 합니다 [1].
3. [1] 현재 설치 디렉터리는 `uv python dir` 명령으로 확인할 수 있습니다 [1].

**핵심 요점**:

0. Names `UV_PYTHON_INSTALL_DIR`.
1. Identifies it as controlling the Python installation directory.

**금지 내용**:

0. Claims `UV_PYTHON_BIN_DIR` changes the managed Python installation directory.

<details><summary>근거 문서</summary>

**[1] reference/storage.md**

```text
### Python versions

uv can install managed [Python versions](../concepts/python-versions.md), e.g., with
`uv python install`.

By default, Python versions managed by uv are stored in a `python/` subdirectory of the
[persistent data directory](#persistent-data-directory), e.g., `~/.local/share/uv/python`.

Use `uv python dir` to show the Python installation directory.

Use the `UV_PYTHON_INSTALL_DIR` environment variable to override the installation directory.

!!! note

    Changing where Python is installed will not be automatically reflected in existing virtual environments; they will keep referring to the old location, and will need to be updated manually (e.g. by re-creating them).

### Python executables

uv installs executables for [Python versions](#python-versions), e.g., `python3.13`.

By default, Python executables are stored in the [executable directory](#executable-directory).

Use `uv python dir --bin` to show the Python executable directory.

Use the `UV_PYTHON_BIN_DIR` environment variable to override the Python executable directory.

### Tools

uv can install Python packages as [command-line tools](../concepts/tools.md) using
`uv tool install`.

By default, tools are installed in a `tools/` subdirectory of the
[persistent data directory](#persistent-data-directory), e.g., `~/.local/share/uv/tools`.

Use `uv tool dir` to show the tool installation directory.

Use the `UV_TOOL_DIR` environment variable to configure the installation directory.

### Tool executables

uv installs executables for installed [tools](#tools), e.g., `ruff`.

By default, tool executables are stored in the [executable directory](#executable-directory).

Use `uv tool dir --bin` to show the tool executable directory.

Use the `UV_TOOL_BIN_DIR` environment variable to configure the tool executable directory.

### The uv executable

When using uv's [standalone installer](./installer.md) to install uv, the `uv` and `uvx` executables
are installed into the [executable directory](#executable-directory).

Use the `UV_INSTALL_DIR` environment variable to configure uv's installation directory.

### Configuration files

uv's behavior can be configured through TOML files.

Configuration files are discovered in the [configuration directories](#configuration-directories).

For more details, see the [configuration files documentation](../concepts/configuration-files.md).
```

**[2] index.md**

```text
## Python versions

uv installs Python and allows quickly switching between versions.

Install multiple Python versions:

```console
$ uv python install 3.10 3.11 3.12
Searching for Python versions matching: Python 3.10
Searching for Python versions matching: Python 3.11
Searching for Python versions matching: Python 3.12
Installed 3 versions in 3.42s
 + cpython-3.10.14-macos-aarch64-none
 + cpython-3.11.9-macos-aarch64-none
 + cpython-3.12.4-macos-aarch64-none
```

Download Python versions as needed:

```console
$ uv venv --python 3.12.0
Using CPython 3.12.0
Creating virtual environment at: .venv
Activate with: source .venv/bin/activate

$ uv run --python pypy@3.8 -- python
Python 3.8.16 (a9dbdca6fc3286b0addd2240f11d97d8e8de187a, Dec 29 2022, 11:45:30)
[PyPy 7.3.11 with GCC Apple LLVM 13.1.6 (clang-1316.0.21.2.5)] on darwin
Type "help", "copyright", "credits" or "license" for more information.
>>>>
```

Use a specific Python version in the current directory:

```console
$ uv python pin 3.11
Pinned `.python-version` to `3.11`
```

See the [installing Python guide](./guides/install-python.md) to get started.
```

**[3] guides/install-python.md**

```text
# Installing Python

If Python is already installed on your system, uv will
[detect and use](#using-existing-python-versions) it without configuration. However, uv can also
install and manage Python versions. uv [automatically installs](#automatic-python-downloads) missing
Python versions as needed — you don't need to install Python to get started.

## Getting started

To install the latest Python version:

```console
$ uv python install
```

!!! note

    Python does not publish official distributable binaries. As such, uv uses distributions from the Astral [`python-build-standalone`](https://github.com/astral-sh/python-build-standalone) project. See the [Python distributions](../concepts/python-versions.md#managed-python-distributions) documentation for more details.

Once Python is installed, it will be used by `uv` commands automatically. uv also adds the installed
version to your `PATH`:

```console
$ python3.15
```

uv only installs a _versioned_ executable by default. To install `python` and `python3` executables,
include the experimental `--default` option:

```console
$ uv python install --default
```

!!! tip

    See the documentation on [installing Python executables](../concepts/python-versions.md#installing-python-executables)
    for more details.

## Installing a specific version

To install a specific Python version:

```console
$ uv python install 3.12
```

To install multiple Python versions:

```console
$ uv python install 3.11 3.12
```

To install an alternative Python implementation, e.g., PyPy:

```console
$ uv python install pypy@3.10
```

See the [`python install`](../concepts/python-versions.md#installing-a-python-version) documentation
for more details.

## Reinstalling Python

To reinstall uv-managed Python versions, use `--reinstall`, e.g.:

```console
$ uv python install --reinstall
```

This will reinstall all previously installed Python versions. Improvements are constantly being
added to the Python distributions, so reinstalling may resolve bugs even if the Python version does
not change.
```

**[4] concepts/python-versions.md**

```text
### Installing Python executables

uv installs Python executables into your `PATH` by default, e.g., on Unix `uv python install 3.12`
will install a Python executable into `~/.local/bin`, e.g., as `python3.12`. See the
[storage documentation](../reference/storage.md#python-executables) for more details about the
target directory.

!!! tip

    If `~/.local/bin` is not in your `PATH`, you can add it with `uv python update-shell`.

To install `python` and `python3` executables, include the experimental `--default` option:

```console
$ uv python install 3.12 --default
```

When installing Python executables, uv will only overwrite an existing executable if it is managed
by uv — e.g., if `~/.local/bin/python3.12` exists already uv will not overwrite it without the
`--force` flag.

uv will update executables that it manages. However, it will prefer the latest patch version of each
Python minor version by default. For example:

```console
$ uv python install 3.12.7  # Adds `python3.12` to `~/.local/bin`
$ uv python install 3.12.6  # Does not update `python3.12`
$ uv python install 3.12.8  # Updates `python3.12` to point to 3.12.8
```
```

**[5] guides/integration/gitlab.md**

```text
## Using `uv pip`

If using the `uv pip` interface instead of the uv project interface, uv requires a virtual
environment by default. To allow installing packages into the system environment, use the `--system`
flag on all uv invocations or set the `UV_SYSTEM_PYTHON` variable.

The `UV_SYSTEM_PYTHON` variable can be defined at different scopes. You can read more about
how [variables and their precedence works in GitLab here](https://docs.gitlab.com/ee/ci/variables/).

Opt-in for the entire workflow by defining it at the top level:

```yaml title=".gitlab-ci.yml"
variables:
  UV_SYSTEM_PYTHON: 1

# [...]
```

To opt-out again, the `--no-system` flag can be used in any uv invocation.

When persisting the cache, you may want to use `requirements.txt` or `pyproject.toml` as
your cache key files instead of `uv.lock`.
```

</details>

## 3. `a17820c2-3581-558d-bda9-a23861efd0fe` (factual, ko)

**질문**: `uv pip compile some/path/pyproject.toml --group foo`를 실행하면 uv는 `foo` 의존성 그룹을 찾기 위해 어떤 파일을 사용하나요?

**답**:

```text
uv는 `some/path/pyproject.toml`이 아니라 현재 디렉터리의 `./pyproject.toml`에서 `foo` 그룹을 찾습니다 [1]. 문서에서는 `uv pip compile some/path/pyproject.toml --group foo`가 `foo`를 `some/path/pyproject.toml`이 아닌 `./pyproject.toml`에서 가져온다고 설명합니다 [1].
```

**인용 판정 대상**(문장, 가리키는 근거 번호):

0. [1] uv는 `some/path/pyproject.toml`이 아니라 현재 디렉터리의 `./pyproject.toml`에서 `foo` 그룹을 찾습니다 [1].
1. [1] 문서에서는 `uv pip compile some/path/pyproject.toml --group foo`가 `foo`를 `some/path/pyproject.toml`이 아닌 `./pyproject.toml`에서 가져온다고 설명합니다 [1].

**핵심 요점**:

0. Identifies `./pyproject.toml` as the source of the group.
1. Makes clear that the file is in the current directory.

**금지 내용**:

0. Claims the group is sourced from `some/path/pyproject.toml`.

<details><summary>근거 문서</summary>

**[1] pip/compile.md**

```text
```console
$ uv pip compile --project some/path/ --group foo --group bar
```

Alternatively, you can specify a path to a `pyproject.toml` for each group:

```console
$ uv pip compile --group some/path/pyproject.toml:foo --group other/pyproject.toml:bar
```

!!! note

    `--group` flags do not apply to other specified sources. For instance,
    `uv pip compile some/path/pyproject.toml --group foo` sources `foo`
    from `./pyproject.toml` and **not** `some/path/pyproject.toml`.
```

**[2] pip/compile.md**

```text
## Locking requirements

uv allows dependencies to be locked in the `requirements.txt` format. It is recommended to use the
standard `pyproject.toml` to define dependencies, but other dependency formats are supported as
well. See the documentation on [declaring dependencies](dependencies.md) for more details on how to
define dependencies.

To lock dependencies declared in a `pyproject.toml`:

```console
$ uv pip compile pyproject.toml -o requirements.txt
```

By default, `uv pip compile` displays its output. Use the `--output-file` / `-o` argument to write
it to a file.

To lock dependencies declared in a `requirements.in`:

```console
$ uv pip compile requirements.in -o requirements.txt
```

To lock dependencies declared in multiple files:

```console
$ uv pip compile pyproject.toml requirements-dev.in -o requirements-dev.txt
```

uv also supports legacy `setup.py` and `setup.cfg` formats. To lock dependencies declared in a
`setup.py`:

```console
$ uv pip compile setup.py -o requirements.txt
```

To lock dependencies from stdin, use `-`:

```console
$ echo "ruff" | uv pip compile -
```

To lock with optional dependencies enabled, e.g., the "foo" extra:

```console
$ uv pip compile pyproject.toml --extra foo
```

To lock with all optional dependencies enabled:

```console
$ uv pip compile pyproject.toml --all-extras
```

Note extras are not supported with the `requirements.in` format.

To lock a dependency group in the current project directory's `pyproject.toml`, for example the
group `foo`:

```console
$ uv pip compile --group foo
```

!!! important

    A `--group` flag has to be added to pip-tools' `pip compile`, [although they're considering it](https://github.com/jazzband/pip-tools/issues/2062). We expect to support whatever syntax and semantics they adopt.

To specify the project directory where groups should be sourced from:

```console
$ uv pip compile --project some/path/ --group foo --group bar
```

Alternatively, you can specify a path to a `pyproject.toml` for each group:

```console
$ uv pip compile --group some/path/pyproject.toml:foo --group other/pyproject.toml:bar
```

!!! note
```

**[3] pip/packages.md**

```text
## Installing packages from files

Multiple packages can be installed at once from standard file formats.

Install from a `requirements.txt` file:

```console
$ uv pip install -r requirements.txt
```

See the [`uv pip compile`](./compile.md) documentation for more information on `requirements.txt`
files.

Install from a `pyproject.toml` file:

```console
$ uv pip install -r pyproject.toml
```

Install from a `pyproject.toml` file with optional dependencies enabled, e.g., the "foo" extra:

```console
$ uv pip install -r pyproject.toml --extra foo
```

Install from a `pyproject.toml` file with all optional dependencies enabled:

```console
$ uv pip install -r pyproject.toml --all-extras
```

To install dependency groups in the current project directory's `pyproject.toml`, for example the
group `foo`:

```console
$ uv pip install --group foo
```

To specify the project directory where groups should be sourced from:

```console
$ uv pip install --project some/path/ --group foo --group bar
```

Alternatively, you can specify a path to a `pyproject.toml` for each group:

```console
$ uv pip install --group some/path/pyproject.toml:foo --group other/pyproject.toml:bar
```

!!! note

    As in pip, `--group` flags do not apply to other sources specified with flags like `-r` or `-e`.
    For instance, `uv pip install -r some/path/pyproject.toml --group foo` sources `foo`
    from `./pyproject.toml` and **not** `some/path/pyproject.toml`.

## Uninstalling a package

To uninstall a package, e.g., Flask:

```console
$ uv pip uninstall flask
```

To uninstall multiple packages, e.g., Flask and Ruff:

```console
$ uv pip uninstall flask ruff
```
```

**[4] concepts/projects/dependencies.md**

```text
### Dependency groups

Development dependencies can be divided into multiple groups, using the `--group` flag.

For example, to add a development dependency in the `lint` group:

```console
$ uv add --group lint ruff
```

Which results in the following `[dependency-groups]` definition:

```toml title="pyproject.toml"
[dependency-groups]
dev = [
  "pytest"
]
lint = [
  "ruff"
]
```

Once groups are defined, the `--all-groups`, `--no-default-groups`, `--group`, `--only-group`, and
`--no-group` options can be used to include or exclude their dependencies.

!!! tip

    The `--dev`, `--only-dev`, and `--no-dev` flags are equivalent to `--group dev`,
    `--only-group dev`, and `--no-group dev` respectively.

uv requires that all dependency groups are compatible with each other and resolves all groups
together when creating the lockfile.

If dependencies declared in one group are not compatible with those in another group, uv will fail
to resolve the requirements of the project with an error.

!!! note

    If you have dependency groups that conflict with one another, resolution will fail
    unless you explicitly [declare them as conflicting](./config.md#conflicting-dependencies).

### Nesting groups

A dependency group can include other dependency groups, e.g.:

```toml title="pyproject.toml"
[dependency-groups]
dev = [
  {include-group = "lint"},
  {include-group = "test"}
]
lint = [
  "ruff"
]
test = [
  "pytest"
]
```

An included group's dependencies cannot conflict with the other dependencies declared in a group.
```

**[5] concepts/projects/dependencies.md**

```text
### Default groups

By default, uv includes the `dev` dependency group in the environment (e.g., during `uv run` or
`uv sync`). The default groups to include can be changed using the `tool.uv.default-groups` setting.

```toml title="pyproject.toml"
[tool.uv]
default-groups = ["dev", "foo"]
```

To enable all dependency groups by default, use `"all"` instead of listing group names:

```toml title="pyproject.toml"
[tool.uv]
default-groups = "all"
```

!!! tip

    To disable this behaviour during `uv run` or `uv sync`, use `--no-default-groups`.
    To exclude a specific default group, use `--no-group <name>`.

### Group `requires-python`

By default, dependency groups must be compatible with your project's `requires-python` range.

If a dependency group requires a different range of Python versions than your project, you can
specify a `requires-python` for the group in `[tool.uv.dependency-groups]`, e.g.:

```toml title="pyproject.toml" hl_lines="9-10"
[project]
name = "example"
version = "0.0.0"
requires-python = ">=3.10"

[dependency-groups]
dev = ["pytest"]

[tool.uv.dependency-groups]
dev = {requires-python = ">=3.12"}
```

### Legacy `dev-dependencies`

Before `[dependency-groups]` was standardized, uv used the `tool.uv.dev-dependencies` field to
specify development dependencies, e.g.:

```toml title="pyproject.toml"
[tool.uv]
dev-dependencies = [
  "pytest"
]
```

Dependencies declared in this section will be combined with the contents in the
`dependency-groups.dev`. Eventually, the `dev-dependencies` field will be deprecated and removed.

!!! note

    If a `tool.uv.dev-dependencies` field exists, `uv add --dev` will use the existing section
    instead of adding a new `dependency-groups.dev` section.
```

</details>

## 4. `e483d557-6b8d-5482-adc5-144ecd182d65` (factual, ko)

**질문**: 추이적 의존성을 포함한 모든 빌드 의존성에 해시를 요구하는 uv build 플래그는 무엇인가요?

**답**:

```text
추이적 의존성을 포함한 모든 빌드 의존성에 해시를 요구하려면 `--require-build-hashes` 플래그를 사용합니다[1]. `pyproject.toml`의 `[tool.uv]` 아래에 `require-build-hashes = true`를 설정하는 방법도 있습니다[3].

`--require-build-hashes`는 실험적 기능입니다[3].
```

**인용 판정 대상**(문장, 가리키는 근거 번호):

0. [1] 추이적 의존성을 포함한 모든 빌드 의존성에 해시를 요구하려면 `--require-build-hashes` 플래그를 사용합니다[1].
1. [3] `pyproject.toml`의 `[tool.uv]` 아래에 `require-build-hashes = true`를 설정하는 방법도 있습니다[3].
2. [3] `--require-build-hashes`는 실험적 기능입니다[3].

**핵심 요점**:

0. Identifies `--require-build-hashes`.
1. Applies the requirement to transitive build dependencies.

**금지 내용**:

0. Claims `--require-hashes` alone requires hashes for every transitive build dependency.

<details><summary>근거 문서</summary>

**[1] concepts/projects/build.md**

```text
## Build constraints

`uv build` accepts `--build-constraint`, which can be used to constrain the versions of any build
requirements during the build process. When coupled with `--require-hashes`, uv will enforce that
the requirements used to build the project match specific, known hashes, for reproducibility.

For example, given the following `constraints.txt`:

```text
setuptools==68.2.2 --hash=sha256:b454a35605876da60632df1a60f736524eb73cc47bbc9f3f1ef1b644de74fd2a
```

Running the following would build the project with the specified version of `setuptools`, and verify
that the downloaded `setuptools` distribution matches the specified hash:

```console
$ uv build --build-constraint constraints.txt --require-hashes
```

To require hashes for every build dependency, including transitive dependencies, use
`--require-build-hashes` instead.
```

**[2] pip/compile.md**

```text
## Adding build constraints

Similar to `constraints`, but specifically for build-time dependencies, including those required
when building runtime dependencies.

Build constraint files are `requirements.txt`-like files that constrain build-time requirements.
However, including a package in a build constraints file will _not_ trigger its installation at
build time; instead, constraints apply only when the package is required as a direct or transitive
build-time dependency. Build constraints can be used to add bounds to dependencies that are not
explicitly declared as build-time dependencies of the current project.

For example, if a package defines its build dependencies as follows:

```toml title="pyproject.toml"
[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"
```

Build constraints could be used to ensure that a specific version of `setuptools` is used for every
package in the workspace:

```requirements title="build-constraints.txt"
setuptools==75.0.0
```

uv will also read `build-constraint-dependencies` from the `pyproject.toml` at the workspace root,
and append them to those specified in the build constraints file.

To require hashes for build dependencies, add them to a build constraints file:

```requirements title="build-constraints.txt"
setuptools==83.0.0 --hash=sha256:29b23c360f22f414dc7336bb39178cc7bcbf6021ed2733cde173f09dba19abb3
```

Then pass the file with `--require-build-hashes`:

```console
$ uv pip compile requirements.in --build-constraint build-constraints.txt --require-build-hashes
```

This option only applies to build dependencies. To check runtime dependencies with `uv pip install`
or `uv pip sync`, use `--require-hashes`. For details and limitations, see
[project build dependency hashes](../concepts/projects/build.md#project-build-dependency-hashes).
```

**[3] concepts/projects/build.md**

```text
### Project build dependency hashes

For example, to verify build dependencies during project resolution and installation, add hashes to
[`build-constraint-dependencies`](../../reference/settings.md#build-constraint-dependencies) in your
workspace's `pyproject.toml`:

```toml
[tool.uv]
build-constraint-dependencies = [
    { requirement = "setuptools==68.2.2", hashes = ["sha256:b454a35605876da60632df1a60f736524eb73cc47bbc9f3f1ef1b644de74fd2a"] },
    "wheel<1",
]
```

uv checks supplied hashes when it downloads pinned build dependencies. Constraints without hashes,
such as `wheel<1`, are also allowed. To require a hash for every build dependency, including
transitive dependencies, set
[`require-build-hashes = true`](../../reference/settings.md#require-build-hashes) under `[tool.uv]`
or pass `--require-build-hashes`.

You'll need to pin each build dependency to an exact version (or use a direct URL) and provide a
hash. Hashes can also come from URL fragments in `build-system.requires`, but not from requirements
returned by a build backend.

When build isolation is disabled, uv uses the installed build dependencies without checking their
hashes. uv also does not recheck already-installed packages or previously built wheels. The bundled
`uv_build` backend does not need a hash because it is part of the uv executable.

!!! note

    `--require-build-hashes` is experimental. Use `--preview-features build-dependency-hashes` to
    suppress the warning.

## Preventing publish to PyPI

If you have internal packages that you do not want to be published, you can mark them as private:

```toml
[project]
classifiers = ["Private :: Do Not Upload"]
```

This setting makes PyPI reject your uploaded package from publishing. It does not affect security or
privacy settings on alternative registries.

We also recommend only generating [per-project PyPI API tokens](https://pypi.org/help/#apitoken):
Without a PyPI token matching the project, it can't be accidentally published.
```

**[4] concepts/projects/config.md**

```text
[project.optional-dependencies]
build = ["setuptools", "cython"]

[tool.uv]
no-build-isolation-package = ["cchardet"]
```

Given the above, a user would first sync with the `build` optional group, and then without it to
remove the build dependencies:

```console
$ uv sync --extra build
 + cchardet==2.1.7
 + cython==3.1.3
 + setuptools==80.9.0
$ uv sync
 - cython==3.1.3
 - setuptools==80.9.0
```

Some packages, like `cchardet`, only require build dependencies for the _installation_ phase of
`uv sync`. Others require their build dependencies to be present even just to resolve the project's
dependencies during the _resolution_ phase.

In such cases, the build dependencies can be installed prior to running any `uv lock` or `uv sync`
commands, using the lower-level `uv pip` API. For example, given:

```toml title="pyproject.toml"
[project]
name = "project"
version = "0.1.0"
description = "..."
readme = "README.md"
requires-python = ">=3.12"
dependencies = ["flash-attn"]

[tool.uv]
no-build-isolation-package = ["flash-attn"]
```

You could run the following sequence of commands to sync `flash-attn`:

```console
$ uv venv
$ uv pip install torch setuptools
$ uv sync
```

Alternatively, users can instead provide the `flash-attn` metadata upfront via the
[`dependency-metadata`](../../reference/settings.md#dependency-metadata) setting, thereby forgoing
the need to build the package during the dependency resolution phase. For example, to provide the
`flash-attn` metadata upfront:

```toml title="pyproject.toml"
[[tool.uv.dependency-metadata]]
name = "flash-attn"
version = "2.6.3"
requires-dist = ["torch", "einops"]
```
```

**[5] concepts/projects/config.md**

```text
#### Dynamic metadata

The use of `match-runtime = true` is only available for packages like `flash-attn` that declare
static metadata. If static metadata is unavailable, uv is required to build the package during the
dependency resolution phase; as such, uv cannot determine the version of the build dependency that
would ultimately be installed in the project environment.

In other words, if `flash-attn` did not declare static metadata, uv would not be able to determine
the version of `torch` that would be installed in the project environment, since it would need to
build `flash-attn` prior to resolving the `torch` version.

As a concrete example, [`axolotl`](https://pypi.org/project/axolotl/) is a popular package that
requires augmented build dependencies, but does not declare static metadata, as the package's
dependencies vary based on the version of `torch` that is installed in the project environment. In
this case, users should instead specify the exact version of `torch` that they intend to use in
their project, and then augment the build dependencies with that version.

For example, to build `axolotl` against `torch==2.6.0`, include the following in your
`pyproject.toml`:

```toml title="pyproject.toml"
[project]
name = "project"
version = "0.1.0"
description = "..."
readme = "README.md"
requires-python = ">=3.12"
dependencies = ["axolotl[deepspeed, flash-attn]", "torch==2.6.0"]

[tool.uv.extra-build-dependencies]
axolotl = ["torch==2.6.0"]
deepspeed = ["torch==2.6.0"]
flash-attn = ["torch==2.6.0"]
```
```

</details>

## 5. `fc26d33c-8f76-5770-9ffe-dee3bdc244fd` (factual, ko)

**질문**: 미리 빌드된 휠이 없는 플랫폼에서 PyPI를 통해 uv를 설치하면 어떻게 되나요?

**답**:

```text
uv는 여러 플랫폼용 사전 빌드된 배포본(wheel)을 제공합니다. 해당 플랫폼용 wheel이 없으면 uv는 소스에서 빌드되며, 이때는 Rust 툴체인이 필요합니다 [1]. 소스에서 빌드하는 방법은 기여자 설정 가이드에 나와 있습니다 [1].
```

**인용 판정 대상**(문장, 가리키는 근거 번호):

0. [1] 해당 플랫폼용 wheel이 없으면 uv는 소스에서 빌드되며, 이때는 Rust 툴체인이 필요합니다 [1].
1. [1] 소스에서 빌드하는 방법은 기여자 설정 가이드에 나와 있습니다 [1].

**핵심 요점**:

0. Says uv is built from source.
1. Says a Rust toolchain is required.

**금지 내용**:

0. Says installation cannot proceed on a platform without a prebuilt wheel.

<details><summary>근거 문서</summary>

**[1] getting-started/installation.md**

```text
### PyPI

For convenience, uv is published to [PyPI](https://pypi.org/project/uv/).

If installing from PyPI, we recommend installing uv into an isolated environment, e.g., with `pipx`:

```console
$ pipx install uv
```

However, `pip` can also be used:

```console
$ pip install uv
```

!!! note

    uv ships with prebuilt distributions (wheels) for many platforms; if a wheel is not available for a given
    platform, uv will be built from source, which requires a Rust toolchain. See the
    [contributing setup guide](https://github.com/astral-sh/uv/blob/main/CONTRIBUTING.md#setup)
    for details on building uv from source.

### Homebrew

uv is available in the core Homebrew packages.

```console
$ brew install uv
```

### MacPorts

uv is available via [MacPorts](https://ports.macports.org/port/uv/).

```console
$ sudo port install uv
```

### WinGet

uv is available via [WinGet](https://winstall.app/apps/astral-sh.uv).

```console
$ winget install --id=astral-sh.uv  -e
```

### Scoop

uv is available via [Scoop](https://scoop.sh/#/apps?q=uv).

```console
$ scoop install main/uv
```

### Docker

uv provides a Docker image at
[`ghcr.io/astral-sh/uv`](https://github.com/astral-sh/uv/pkgs/container/uv).

See our guide on [using uv in Docker](../guides/integration/docker.md) for more details.

### GitHub Releases

uv release artifacts can be downloaded directly from
[GitHub Releases](https://github.com/astral-sh/uv/releases).

Each release page includes binaries for all supported platforms as well as instructions for using
the standalone installer via `github.com` instead of `astral.sh`.

### Cargo

uv is available via [crates.io](https://crates.io).

```console
$ cargo install --locked uv
```

!!! note

    This method builds uv from source, which requires a compatible Rust toolchain.
```

**[2] index.md**

```text
# uv

An extremely fast Python package and project manager, written in Rust.

  

  

  Installing Trio's dependencies with a warm cache.

## Highlights

- A single tool to replace `pip`, `pip-tools`, `pipx`, `poetry`, `pyenv`, `twine`, `virtualenv`, and
  more.
- [10-100x faster](https://github.com/astral-sh/uv/blob/main/BENCHMARKS.md) than `pip`.
- Provides [comprehensive project management](#projects), with a
  [universal lockfile](./concepts/projects/layout.md#the-lockfile).
- [Runs scripts](#scripts), with support for
  [inline dependency metadata](./guides/scripts.md#declaring-script-dependencies).
- [Installs and manages](#python-versions) Python versions.
- [Runs and installs](#tools) tools published as Python packages.
- Includes a [pip-compatible interface](#the-pip-interface) for a performance boost with a familiar
  CLI.
- Supports Cargo-style [workspaces](./concepts/projects/workspaces.md) for scalable projects.
- Disk-space efficient, with a [global cache](./concepts/cache.md) for dependency deduplication.
- Installable without Rust or Python via `curl` or `pip`.
- Supports macOS, Linux, and Windows.

uv is backed by [Astral](https://astral.sh), the creators of
[Ruff](https://github.com/astral-sh/ruff).

## Installation

Install uv with our official standalone installer:

=== "macOS and Linux"

    ```console
    $ curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

=== "Windows"

    ```pwsh-session
    PS> powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

Then, check out the [first steps](./getting-started/first-steps.md) or read on for a brief overview.

!!! tip

    uv may also be installed with pip, Homebrew, and more. See all of the methods on the
    [installation page](./getting-started/installation.md).
```

**[3] getting-started/features.md**

```text
# Features

uv provides essential features for Python development — from installing Python and hacking on simple
scripts to working on large projects that support multiple Python versions and platforms.

uv's interface can be broken down into sections, which are usable independently or together.

## Python versions

Installing and managing Python itself.

- `uv python install`: Install Python versions.
- `uv python list`: View available Python versions.
- `uv python find`: Find an installed Python version.
- `uv python pin`: Pin the current project to use a specific Python version.
- `uv python uninstall`: Uninstall a Python version.

See the [guide on installing Python](../guides/install-python.md) to get started.

## Scripts

Executing standalone Python scripts, e.g., `example.py`.

- `uv run`: Run a script.
- `uv add --script`: Add a dependency to a script.
- `uv remove --script`: Remove a dependency from a script.

See the [guide on running scripts](../guides/scripts.md) to get started.

## Projects

Creating and working on Python projects, i.e., with a `pyproject.toml`.

- `uv init`: Create a new Python project.
- `uv add`: Add a dependency to the project.
- `uv remove`: Remove a dependency from the project.
- `uv sync`: Sync the project's dependencies with the environment.
- `uv lock`: Create a lockfile for the project's dependencies.
- `uv run`: Run a command in the project environment.
- `uv tree`: View the dependency tree for the project.
- `uv build`: Build the project into distribution archives.
- `uv publish`: Publish the project to a package index.

See the [guide on projects](../guides/projects.md) to get started.

## Tools

Running and installing tools published to Python package indexes, e.g., `ruff` or `black`.

- `uvx` / `uv tool run`: Run a tool in a temporary environment.
- `uv tool install`: Install a tool user-wide.
- `uv tool uninstall`: Uninstall a tool.
- `uv tool list`: List installed tools.
- `uv tool update-shell`: Update the shell to include tool executables.

See the [guide on tools](../guides/tools.md) to get started.
```

**[4] guides/install-python.md**

```text
# Installing Python

If Python is already installed on your system, uv will
[detect and use](#using-existing-python-versions) it without configuration. However, uv can also
install and manage Python versions. uv [automatically installs](#automatic-python-downloads) missing
Python versions as needed — you don't need to install Python to get started.

## Getting started

To install the latest Python version:

```console
$ uv python install
```

!!! note

    Python does not publish official distributable binaries. As such, uv uses distributions from the Astral [`python-build-standalone`](https://github.com/astral-sh/python-build-standalone) project. See the [Python distributions](../concepts/python-versions.md#managed-python-distributions) documentation for more details.

Once Python is installed, it will be used by `uv` commands automatically. uv also adds the installed
version to your `PATH`:

```console
$ python3.15
```

uv only installs a _versioned_ executable by default. To install `python` and `python3` executables,
include the experimental `--default` option:

```console
$ uv python install --default
```

!!! tip

    See the documentation on [installing Python executables](../concepts/python-versions.md#installing-python-executables)
    for more details.

## Installing a specific version

To install a specific Python version:

```console
$ uv python install 3.12
```

To install multiple Python versions:

```console
$ uv python install 3.11 3.12
```

To install an alternative Python implementation, e.g., PyPy:

```console
$ uv python install pypy@3.10
```

See the [`python install`](../concepts/python-versions.md#installing-a-python-version) documentation
for more details.

## Reinstalling Python

To reinstall uv-managed Python versions, use `--reinstall`, e.g.:

```console
$ uv python install --reinstall
```

This will reinstall all previously installed Python versions. Improvements are constantly being
added to the Python distributions, so reinstalling may resolve bugs even if the Python version does
not change.
```

**[5] getting-started/first-steps.md**

```text
# First steps with uv

After [installing uv](./installation.md), you can check that uv is available by running the `uv`
command:

```console
$ uv
An extremely fast Python package manager.

Usage: uv [OPTIONS] <COMMAND>

...
```

You should see a help menu listing the available commands.

## Next steps

Now that you've confirmed uv is installed, check out an [overview of features](./features.md), learn
how to [get help](./help.md) if you run into any problems, or jump to the
[guides](../guides/index.md) to start using uv.
```

</details>

## 6. `37953282-33db-5581-939c-4066715c9d3c` (multi_doc, ko)

**질문**: `project/app`에 기존 FastAPI 앱이 있는데, uv의 기본 애플리케이션 레이아웃을 사용하는 대신 패키지화하지 않은 상태로 유지하고 싶습니다. `project`에서 어떤 명령을 실행해야 FastAPI의 standard extras를 포함해 설정하고 개발 서버를 시작할 수 있나요? 이 방식은 기본 uv 애플리케이션 설정과 어떻게 다른가요?

**답**:

```text
`project` 디렉터리에서 다음 명령을 순서대로 실행하면 됩니다.

```console
$ uv init --no-package
$ uv add fastapi --extra standard
$ uv run fastapi dev
```

첫 명령은 패키지화하지 않은 평평한(flat) 프로젝트용 `pyproject.toml`을 만듭니다 [2]. 두 번째 명령은 FastAPI를 의존성으로 추가합니다 [2]. 세 번째 명령인 `uv run fastapi dev`는 FastAPI 애플리케이션을 실행합니다 [2]. `uv run`은 프로젝트 의존성을 자동으로 resolve하고 lock하며(`uv.lock` 생성), 가상 환경을 만들고, 그 환경에서 명령을 실행합니다 [2]. 실행 후 웹 브라우저에서 http://127.0.0.1:8000/?token=jessica 를 열어 앱을 테스트할 수 있습니다 [2].

기본 uv 애플리케이션 설정과의 차이는 다음과 같습니다.

- 기본 `uv init`은 애플리케이션 프로젝트를 만드는 기본 대상이며 [4], 소스 코드는 `src` 디렉터리 아래의 모듈 디렉터리에 위치합니다 [4].
- 기본 애플리케이션 프로젝트에는 빌드 시스템이 정의되어 있어 프로젝트가 환경에 설치됩니다 [4]. 또한 `[project.scripts]` 명령 정의가 포함됩니다 [4].
- 반면 `--no-package`로 만든 프로젝트는 빌드 시스템 없이 패키지화하지 않은 프로젝트를 가리키는 문서 섹션과 연결됩니다 [2]. 문서의 예시 `pyproject.toml`에도 `[build-system]` 섹션이 없습니다 [2].
- 이 방식에서는 기존 `project/app` 구조를 그대로 두고 [2], `pyproject.toml`에 `fastapi[standard]` 의존성이 들어갑니다 [2].
```

**인용 판정 대상**(문장, 가리키는 근거 번호):

0. [2] 첫 명령은 패키지화하지 않은 평평한(flat) 프로젝트용 `pyproject.toml`을 만듭니다 [2].
1. [2] 두 번째 명령은 FastAPI를 의존성으로 추가합니다 [2].
2. [2] 세 번째 명령인 `uv run fastapi dev`는 FastAPI 애플리케이션을 실행합니다 [2].
3. [2] `uv run`은 프로젝트 의존성을 자동으로 resolve하고 lock하며(`uv.lock` 생성), 가상 환경을 만들고, 그 환경에서 명령을 실행합니다 [2].
4. [2] 실행 후 웹 브라우저에서 http://127.0.0.1:8000/?token=jessica 를 열어 앱을 테스트할 수 있습니다 [2].
5. [4] - 기본 `uv init`은 애플리케이션 프로젝트를 만드는 기본 대상이며 [4], 소스 코드는 `src` 디렉터리 아래의 모듈 디렉터리에 위치합니다 [4].
6. [4] - 기본 애플리케이션 프로젝트에는 빌드 시스템이 정의되어 있어 프로젝트가 환경에 설치됩니다 [4].
7. [4] 또한 `[project.scripts]` 명령 정의가 포함됩니다 [4].
8. [2] - 반면 `--no-package`로 만든 프로젝트는 빌드 시스템 없이 패키지화하지 않은 프로젝트를 가리키는 문서 섹션과 연결됩니다 [2].
9. [2] 문서의 예시 `pyproject.toml`에도 `[build-system]` 섹션이 없습니다 [2].
10. [2] - 이 방식에서는 기존 `project/app` 구조를 그대로 두고 [2], `pyproject.toml`에 `fastapi[standard]` 의존성이 들어갑니다 [2].

**핵심 요점**:

0. Says to run `uv init --no-package` from the project directory.
1. Says to run `uv add fastapi --extra standard`.
2. Says to start the development server with `uv run fastapi dev`.
3. Explains that the default application setup defines a build system and uses a `src` layout.
4. Explains that the unpackaged project has no build system and is not installed into the environment.

**금지 내용**:

0. Claims the `--no-package` project is installed into the environment.
1. Claims the default application setup has no build system.

<details><summary>근거 문서</summary>

**[1] guides/integration/fastapi.md**

```text
# Using uv with FastAPI

[FastAPI](https://github.com/fastapi/fastapi) is a modern, high-performance Python web framework.
You can use uv to manage your FastAPI project, including installing dependencies, managing
environments, running FastAPI applications, and more.

!!! note

    You can view the source code for this guide in the [uv-fastapi-example](https://github.com/astral-sh/uv-fastapi-example) repository.
```

**[2] guides/integration/fastapi.md**

```text
## Migrating an existing FastAPI project

As an example, consider the sample application defined in the
[FastAPI documentation](https://fastapi.tiangolo.com/tutorial/bigger-applications/), structured as
follows:

```plaintext
project
└── app
    ├── __init__.py
    ├── main.py
    ├── dependencies.py
    ├── routers
    │   ├── __init__.py
    │   ├── items.py
    │   └── users.py
    └── internal
        ├── __init__.py
        └── admin.py
```

To use uv with this application, inside the `project` directory run:

```console
$ uv init --no-package
```

This creates a `pyproject.toml` file for a
[flat, unpackaged project](../../concepts/projects/init.md#creating-a-project-without-a-build-system).

Then, add a dependency on FastAPI:

```console
$ uv add fastapi --extra standard
```

You should now have the following structure:

```plaintext
project
├── pyproject.toml
└── app
    ├── __init__.py
    ├── main.py
    ├── dependencies.py
    ├── routers
    │   ├── __init__.py
    │   ├── items.py
    │   └── users.py
    └── internal
        ├── __init__.py
        └── admin.py
```

And the contents of the `pyproject.toml` file should look something like this:

```toml title="pyproject.toml"
[project]
name = "uv-fastapi-example"
version = "0.1.0"
description = "FastAPI project"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "fastapi[standard]",
]
```

From there, you can run the FastAPI application with:

```console
$ uv run fastapi dev
```

`uv run` will automatically resolve and lock the project dependencies (i.e., create a `uv.lock`
alongside the `pyproject.toml`), create a virtual environment, and run the command in that
environment.

Test the app by opening http://127.0.0.1:8000/?token=jessica in a web browser.
```

**[3] guides/integration/fastapi.md**

```text
## Deployment

To deploy the FastAPI application with Docker, you can use the following `Dockerfile`:

```dockerfile title="Dockerfile"
FROM python:3.12-slim

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy the application into the container.
COPY . /app

# Install the application dependencies.
WORKDIR /app
RUN uv sync --frozen --no-cache

# Run the application.
CMD ["/app/.venv/bin/fastapi", "run", "app/main.py", "--port", "80", "--host", "0.0.0.0"]
```

Build the Docker image with:

```console
$ docker build -t fastapi-app .
```

Run the Docker container locally with:

```console
$ docker run -p 8000:80 fastapi-app
```

Navigate to http://127.0.0.1:8000/?token=jessica in your browser to verify that the app is running
correctly.

!!! tip

    For more on using uv with Docker, see the [Docker guide](./docker.md).
```

**[4] concepts/projects/init.md**

```text
## Applications

Application projects are suitable for web servers, scripts, and command-line interfaces.

Applications are the default target for `uv init`, but can also be specified with the `--app` flag:

```console
$ uv init example-app
```

The source code lives in a `src` directory with a module directory and an `__init__.py` file:

```console
$ tree example-app
example-app/
├── .python-version
├── README.md
├── pyproject.toml
└── src
    └── example_app
        └── __init__.py
```

A [build system](./config.md#build-systems) is defined, so the project will be installed into the
environment:

```toml title="pyproject.toml" hl_lines="12-14"
[project]
name = "example-app"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.11"
dependencies = []

[project.scripts]
example-app = "example_app:main"

[build-system]
requires = ["uv_build>=0.13.7,<0.14"]
build-backend = "uv_build"
```

!!! tip

    The `--build-backend` option can be used to request an alternative build system.

A [command](./config.md#entry-points) definition is included:

```toml title="pyproject.toml" hl_lines="9 10"
[project]
name = "example-app"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.11"
dependencies = []

[project.scripts]
example-app = "example_app:main"

[build-system]
requires = ["uv_build>=0.13.7,<0.14"]
build-backend = "uv_build"
```

The command can be executed with `uv run`:

```console
$ cd example-app
$ uv run example-app
Hello from example-app!
```
```

**[5] guides/integration/aws-lambda.md**

```text
# Using uv with AWS Lambda

[AWS Lambda](https://aws.amazon.com/lambda/) is a serverless computing service that lets you run
code without provisioning or managing servers.

You can use uv with AWS Lambda to manage your Python dependencies, build your deployment package,
and deploy your Lambda functions.

!!! tip

    Check out the [`uv-aws-lambda-example`](https://github.com/astral-sh/uv-aws-lambda-example) project for
    an example of best practices when using uv to deploy an application to AWS Lambda.

## Getting started

To start, assume we have a minimal FastAPI application with the following structure:

```plaintext
project
├── pyproject.toml
└── app
    ├── __init__.py
    └── main.py
```

Where the `pyproject.toml` contains:

```toml title="pyproject.toml"
[project]
name = "uv-aws-lambda-example"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    # FastAPI is a modern web framework for building APIs with Python.
    "fastapi",
    # Mangum is a library that adapts ASGI applications to AWS Lambda and API Gateway.
    "mangum",
]

[dependency-groups]
dev = [
    # In development mode, include the FastAPI development server.
    "fastapi[standard]>=0.115",
]
```

And the `main.py` file contains:

```python title="app/main.py"
import logging

from fastapi import FastAPI
from mangum import Mangum

logger = logging.getLogger()
logger.setLevel(logging.INFO)

app = FastAPI()
handler = Mangum(app)

@app.get("/")
async def root() -> str:
    return "Hello, world!"
```

We can run this application locally with:

```console
$ uv run fastapi dev
```

From there, opening http://127.0.0.1:8000/ in a web browser will display "Hello, world!"
```

</details>

## 7. `525a1b2f-87c8-504f-9c07-cac8086f76c6` (multi_doc, ko)

**질문**: 최신 Python을 `python`과 `python3` 실행 파일이 모두 포함되도록 설치한 다음, uv로 프로젝트의 의존성 트리를 보려면 어떻게 해야 하나요? 이 설치 옵션은 안정적인가요?

**답**:

```text
최신 Python을 `python`과 `python3` 실행 파일이 모두 포함되도록 설치하려면 다음 명령을 사용합니다.

```console
$ uv python install --default
```

`uv python install`은 기본적으로 버전이 붙은 실행 파일만 설치하며, `python`과 `python3` 실행 파일을 설치하려면 `--default` 옵션을 포함해야 합니다 [3][5]. 이 명령에서 최신 Python 버전이 설치됩니다 [3][4].

그다음 프로젝트의 의존성 트리를 보려면 `uv tree`를 실행합니다.

```console
$ uv tree
```

`uv tree`는 프로젝트의 의존성 트리를 보여주는 명령입니다 [1].

이 설치 옵션은 안정적이지 않습니다. 문서에서는 `--default` 옵션을 experimental(실험적)이라고 설명합니다 [3][5].
```

**인용 판정 대상**(문장, 가리키는 근거 번호):

0. [3] `uv python install`은 기본적으로 버전이 붙은 실행 파일만 설치하며, `python`과 `python3` 실행 파일을 설치하려면 `--default` 옵션을 포함해야 합니다 [3][5].
1. [5] `uv python install`은 기본적으로 버전이 붙은 실행 파일만 설치하며, `python`과 `python3` 실행 파일을 설치하려면 `--default` 옵션을 포함해야 합니다 [3][5].
2. [3] 이 명령에서 최신 Python 버전이 설치됩니다 [3][4].
3. [4] 이 명령에서 최신 Python 버전이 설치됩니다 [3][4].
4. [1] `uv tree`는 프로젝트의 의존성 트리를 보여주는 명령입니다 [1].
5. [3] 문서에서는 `--default` 옵션을 experimental(실험적)이라고 설명합니다 [3][5].
6. [5] 문서에서는 `--default` 옵션을 experimental(실험적)이라고 설명합니다 [3][5].

**핵심 요점**:

0. Uses `uv python install --default` to install Python with the requested executables.
1. Uses `uv tree` to view the project's dependency tree.
2. Identifies `--default` as experimental.

**금지 내용**:

0. Claims that `python` and `python3` are installed by default without `--default`.
1. Presents `--default` as stable.

<details><summary>근거 문서</summary>

**[1] getting-started/features.md**

```text
# Features

uv provides essential features for Python development — from installing Python and hacking on simple
scripts to working on large projects that support multiple Python versions and platforms.

uv's interface can be broken down into sections, which are usable independently or together.

## Python versions

Installing and managing Python itself.

- `uv python install`: Install Python versions.
- `uv python list`: View available Python versions.
- `uv python find`: Find an installed Python version.
- `uv python pin`: Pin the current project to use a specific Python version.
- `uv python uninstall`: Uninstall a Python version.

See the [guide on installing Python](../guides/install-python.md) to get started.

## Scripts

Executing standalone Python scripts, e.g., `example.py`.

- `uv run`: Run a script.
- `uv add --script`: Add a dependency to a script.
- `uv remove --script`: Remove a dependency from a script.

See the [guide on running scripts](../guides/scripts.md) to get started.

## Projects

Creating and working on Python projects, i.e., with a `pyproject.toml`.

- `uv init`: Create a new Python project.
- `uv add`: Add a dependency to the project.
- `uv remove`: Remove a dependency from the project.
- `uv sync`: Sync the project's dependencies with the environment.
- `uv lock`: Create a lockfile for the project's dependencies.
- `uv run`: Run a command in the project environment.
- `uv tree`: View the dependency tree for the project.
- `uv build`: Build the project into distribution archives.
- `uv publish`: Publish the project to a package index.

See the [guide on projects](../guides/projects.md) to get started.

## Tools

Running and installing tools published to Python package indexes, e.g., `ruff` or `black`.

- `uvx` / `uv tool run`: Run a tool in a temporary environment.
- `uv tool install`: Install a tool user-wide.
- `uv tool uninstall`: Uninstall a tool.
- `uv tool list`: List installed tools.
- `uv tool update-shell`: Update the shell to include tool executables.

See the [guide on tools](../guides/tools.md) to get started.
```

**[2] index.md**

```text
# uv

An extremely fast Python package and project manager, written in Rust.

  

  

  Installing Trio's dependencies with a warm cache.

## Highlights

- A single tool to replace `pip`, `pip-tools`, `pipx`, `poetry`, `pyenv`, `twine`, `virtualenv`, and
  more.
- [10-100x faster](https://github.com/astral-sh/uv/blob/main/BENCHMARKS.md) than `pip`.
- Provides [comprehensive project management](#projects), with a
  [universal lockfile](./concepts/projects/layout.md#the-lockfile).
- [Runs scripts](#scripts), with support for
  [inline dependency metadata](./guides/scripts.md#declaring-script-dependencies).
- [Installs and manages](#python-versions) Python versions.
- [Runs and installs](#tools) tools published as Python packages.
- Includes a [pip-compatible interface](#the-pip-interface) for a performance boost with a familiar
  CLI.
- Supports Cargo-style [workspaces](./concepts/projects/workspaces.md) for scalable projects.
- Disk-space efficient, with a [global cache](./concepts/cache.md) for dependency deduplication.
- Installable without Rust or Python via `curl` or `pip`.
- Supports macOS, Linux, and Windows.

uv is backed by [Astral](https://astral.sh), the creators of
[Ruff](https://github.com/astral-sh/ruff).

## Installation

Install uv with our official standalone installer:

=== "macOS and Linux"

    ```console
    $ curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

=== "Windows"

    ```pwsh-session
    PS> powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

Then, check out the [first steps](./getting-started/first-steps.md) or read on for a brief overview.

!!! tip

    uv may also be installed with pip, Homebrew, and more. See all of the methods on the
    [installation page](./getting-started/installation.md).
```

**[3] guides/install-python.md**

```text
# Installing Python

If Python is already installed on your system, uv will
[detect and use](#using-existing-python-versions) it without configuration. However, uv can also
install and manage Python versions. uv [automatically installs](#automatic-python-downloads) missing
Python versions as needed — you don't need to install Python to get started.

## Getting started

To install the latest Python version:

```console
$ uv python install
```

!!! note

    Python does not publish official distributable binaries. As such, uv uses distributions from the Astral [`python-build-standalone`](https://github.com/astral-sh/python-build-standalone) project. See the [Python distributions](../concepts/python-versions.md#managed-python-distributions) documentation for more details.

Once Python is installed, it will be used by `uv` commands automatically. uv also adds the installed
version to your `PATH`:

```console
$ python3.15
```

uv only installs a _versioned_ executable by default. To install `python` and `python3` executables,
include the experimental `--default` option:

```console
$ uv python install --default
```

!!! tip

    See the documentation on [installing Python executables](../concepts/python-versions.md#installing-python-executables)
    for more details.

## Installing a specific version

To install a specific Python version:

```console
$ uv python install 3.12
```

To install multiple Python versions:

```console
$ uv python install 3.11 3.12
```

To install an alternative Python implementation, e.g., PyPy:

```console
$ uv python install pypy@3.10
```

See the [`python install`](../concepts/python-versions.md#installing-a-python-version) documentation
for more details.

## Reinstalling Python

To reinstall uv-managed Python versions, use `--reinstall`, e.g.:

```console
$ uv python install --reinstall
```

This will reinstall all previously installed Python versions. Improvements are constantly being
added to the Python distributions, so reinstalling may resolve bugs even if the Python version does
not change.
```

**[4] concepts/python-versions.md**

```text
## Installing a Python version

uv bundles a list of downloadable CPython and PyPy distributions for macOS, Linux, and Windows.

!!! tip

    By default, Python versions are automatically downloaded as needed without using
    `uv python install`.

To install a Python version at a specific version:

```console
$ uv python install 3.12.3
```

To install the latest patch version:

```console
$ uv python install 3.12
```

To install a version that satisfies constraints:

```console
$ uv python install '>=3.8,<3.10'
```

To install multiple versions:

```console
$ uv python install 3.9 3.10 3.11
```

To install a specific implementation:

```console
$ uv python install pypy
```

All the [Python version request](#requesting-a-version) formats are supported except those that are
used for requesting local interpreters such as a file path.

By default `uv python install` will verify that a managed Python version is installed or install the
latest version. If a `.python-version` file is present, uv will install the Python version listed in
the file. A project that requires multiple Python versions may define a `.python-versions` file. If
present, uv will install all the Python versions listed in the file.

!!! important

    The available Python versions are frozen for each uv release. To install new Python versions,
    you may need to upgrade uv.

See the [storage documentation](../reference/storage.md#python-versions) for details about where
installed Python versions are stored.
```

**[5] concepts/python-versions.md**

```text
### Installing Python executables

uv installs Python executables into your `PATH` by default, e.g., on Unix `uv python install 3.12`
will install a Python executable into `~/.local/bin`, e.g., as `python3.12`. See the
[storage documentation](../reference/storage.md#python-executables) for more details about the
target directory.

!!! tip

    If `~/.local/bin` is not in your `PATH`, you can add it with `uv python update-shell`.

To install `python` and `python3` executables, include the experimental `--default` option:

```console
$ uv python install 3.12 --default
```

When installing Python executables, uv will only overwrite an existing executable if it is managed
by uv — e.g., if `~/.local/bin/python3.12` exists already uv will not overwrite it without the
`--force` flag.

uv will update executables that it manages. However, it will prefer the latest patch version of each
Python minor version by default. For example:

```console
$ uv python install 3.12.7  # Adds `python3.12` to `~/.local/bin`
$ uv python install 3.12.6  # Does not update `python3.12`
$ uv python install 3.12.8  # Updates `python3.12` to point to 3.12.8
```
```

</details>

## 8. `872399ce-bd8c-5707-8526-3ce3b89e8898` (multi_doc, ko)

**질문**: PEP 723 메타데이터가 포함된 `my_notebook.py`라는 marimo 노트북이 있습니다. uv로 이 노트북의 의존성을 잠그려면 어떻게 해야 하고, 그러면 어떤 파일이 생성되나요? 또 브라우저를 열지 않고 노트북을 실행하려면 어떻게 해야 하나요?

**답**:

```text
**잠금 방법과 생성되는 파일**: 문서에는 이 노트북의 의존성을 잠그는 명령이나 그 과정에서 생성되는 파일에 대한 설명이 없습니다. 문서에서 확인되는 것은 `uv add --script my_notebook.py numpy` 명령으로 노트북에 의존성을 추가할 수 있다는 점입니다 [1]. marimo UI에서 설치한 패키지도 노트북의 스크립트 메타데이터에 자동으로 추가됩니다 [1].

**브라우저를 열지 않고 실행하는 방법**: 다음 명령으로 노트북을 Python 스크립트로 실행할 수 있습니다 [1].

```console
$ uv run my_notebook.py
```

이 명령은 대화형 세션을 열지 않고 노트북을 Python 스크립트로 실행합니다 [2].
```

**인용 판정 대상**(문장, 가리키는 근거 번호):

0. [1] 문서에서 확인되는 것은 `uv add --script my_notebook.py numpy` 명령으로 노트북에 의존성을 추가할 수 있다는 점입니다 [1].
1. [1] marimo UI에서 설치한 패키지도 노트북의 스크립트 메타데이터에 자동으로 추가됩니다 [1].
2. [1] **브라우저를 열지 않고 실행하는 방법**: 다음 명령으로 노트북을 Python 스크립트로 실행할 수 있습니다 [1].
3. [2] 이 명령은 대화형 세션을 열지 않고 노트북을 Python 스크립트로 실행합니다 [2].

**핵심 요점**:

0. Gives `uv lock --script my_notebook.py` as the locking command.
1. Identifies `my_notebook.py.lock` alongside the notebook as the created file.
2. Gives `uv run my_notebook.py` as the command to execute the notebook without a browser.

**금지 내용**:

0. Claims that running the notebook automatically creates its script lockfile.
1. Claims that script execution opens an interactive browser session.

<details><summary>근거 문서</summary>

**[1] guides/integration/marimo.md**

```text
# Using uv with marimo

[marimo](https://github.com/marimo-team/marimo) is an open-source Python notebook that blends
interactive computing with the reproducibility and reusability of traditional software, letting you
version with Git, run as scripts, and share as apps. Because marimo notebooks are stored as pure
Python scripts, they are able to integrate tightly with uv.

You can readily use marimo as a standalone tool, as self-contained scripts, in projects, and in
non-project environments.

## Using marimo as a standalone tool

For ad-hoc access to marimo notebooks, start a marimo server at any time in an isolated environment
with:

```console
$ uvx marimo edit
```

Start a specific notebook with:

```console
$ uvx marimo edit my_notebook.py
```

## Using marimo with inline script metadata

Because marimo notebooks are stored as Python scripts, they can encapsulate their own dependencies
using inline script metadata, via uv's [support for scripts](../../guides/scripts.md). For example,
to add `numpy` as a dependency to your notebook, use this command:

```console
$ uv add --script my_notebook.py numpy
```

To interactively edit a notebook containing inline script metadata, use:

```console
$ uvx marimo edit --sandbox my_notebook.py
```

marimo will automatically use uv to start your notebook in an isolated virtual environment with your
script's dependencies. Packages installed from the marimo UI will automatically be added to the
notebook's script metadata.

You can optionally run these notebooks as Python scripts, without opening an interactive session:

```console
$ uv run my_notebook.py
```
```

**[2] guides/integration/marimo.md**

```text
## Using marimo within a project

If you're working within a [project](../../concepts/projects/index.md), you can start a marimo
notebook with access to the project's virtual environment via the following command (assuming marimo
is a project dependency):

```console
$ uv run marimo edit my_notebook.py
```

To make additional packages available to your notebook, either add them to your project with
`uv add`, or use marimo's built-in package installation UI, which will invoke `uv add` on your
behalf.

If marimo is not a project dependency, you can still run a notebook with the following command:

```console
$ uv run --with marimo marimo edit my_notebook.py
```

This will let you import your project's modules while editing your notebook. However, packages
installed via marimo's UI when running in this way will not be added to your project, and may
disappear on subsequent marimo invocations.

## Using marimo in a non-project environment

To run marimo in a virtual environment that isn't associated with a
[project](../../concepts/projects/index.md), add marimo to the environment directly:

```console
$ uv venv
$ uv pip install numpy
$ uv pip install marimo
$ uv run marimo edit
```

From here, `import numpy` will work within the notebook, and marimo's UI installer will add packages
to the environment with `uv pip install` on your behalf.

## Running marimo notebooks as scripts

Regardless of how your dependencies are managed (with inline script metadata, within a project, or
with a non-project environment), you can run marimo notebooks as scripts with:

```console
$ uv run my_notebook.py
```

This executes your notebook as a Python script, without opening an interactive session in your
browser.
```

**[3] guides/integration/index.md**

```text
# Integration guides

Learn how to integrate uv with other software:

- [Using in Docker images](./docker.md)
- [Using with Jupyter notebooks](./jupyter.md)
- [Using with marimo notebooks](./marimo.md)
- [Using with pre-commit](./pre-commit.md)
- [Using in GitHub Actions](./github.md)
- [Using in GitLab CI/CD](./gitlab.md)
- [Installing PyTorch](./pytorch.md)
- [Building a FastAPI application](./fastapi.md)
- [Using with Bazel](./bazel.md)
- [Using with Azure Artifacts](./azure.md)
- [Using with Google Artifact Registry](./google.md)
- [Using with AWS CodeArtifact](./aws.md)
- [Using with JFrog Artifactory](./jfrog.md)
- [Using with Renovate](./renovate.md)
- [Using with Dependabot](./dependabot.md)
- [Using with AWS Lambda](./aws-lambda.md)
- [Using with Coiled](./coiled.md)

Or, explore the [concept documentation](../../concepts/index.md) for a comprehensive breakdown of
each feature.
```

**[4] guides/integration/jupyter.md**

```text
# Using uv with Jupyter

The [Jupyter](https://jupyter.org/) notebook is a popular tool for interactive computing, data
analysis, and visualization. You can use Jupyter with uv in a few different ways, either to interact
with a project, or as a standalone tool.

## Using Jupyter within a project

If you're working within a [project](../../concepts/projects/index.md), you can start a Jupyter
server with access to the project's virtual environment via the following:

```console
$ uv run --with jupyter jupyter lab
```

By default, `jupyter lab` will start the server at
[http://localhost:8888/lab](http://localhost:8888/lab).

Within a notebook, you can import your project's modules as you would in any other file in the
project. For example, if your project depends on `requests`, `import requests` will import
`requests` from the project's virtual environment.

If you're looking for read-only access to the project's virtual environment, then there's nothing
more to it. However, if you need to install additional packages from within the notebook, there are
a few extra details to consider.
```

**[5] concepts/projects/workspaces.md**

```text
!!! note

    As Python does not provide dependency isolation, uv can't ensure that a package uses its declared dependencies and nothing else. For workspaces specifically, uv can't ensure that packages don't import dependencies declared by another workspace member.
```

</details>

## 9. `b5a16aea-7087-5cdb-bfe5-fba043ad5644` (multi_doc, ko)

**질문**: 잠긴 다른 패키지는 업데이트하지 않고 requests만 호환되는 최신 버전으로 업데이트한 다음, 로컬 경로를 기존 release 디렉터리 기준 상대 경로로 하여 PEP 751 lockfile을 그 디렉터리에 내보내려면 어떻게 해야 하나요?

**답**:

```text
문서에 있는 범위에서는 다음 순서로 진행할 수 있습니다. 다만 release 디렉터리를 기준으로 한 상대 경로 지정 방법은 문서에 없어서 확인할 수 없습니다.

1. **requests만 업그레이드:** `uv lock --upgrade-package requests`를 실행합니다. 이 플래그는 지정한 패키지를 최신 호환 버전으로 올리고 나머지 lockfile 내용은 그대로 둡니다 [1][2]. 업그레이드는 프로젝트의 의존성 제약 범위를 넘지 않습니다 [2].

2. **PEP 751 형식으로 내보내기:** `uv export -o pylock.toml` 또는 `uv export --format pylock.toml`을 사용합니다 [3][2]. `-o`로 출력 파일을 지정할 수 있습니다 [3].

3. **release 디렉터리 기준 상대 경로:** 제공된 문서에는 `-o`에 상대 경로를 지정했을 때 어느 디렉터리를 기준으로 해석되는지, 또는 release 디렉터리에 어떻게 쓰는지에 대한 내용이 없습니다. 따라서 이 부분은 문서만으로는 답할 수 없습니다.
```

**인용 판정 대상**(문장, 가리키는 근거 번호):

0. [1] 이 플래그는 지정한 패키지를 최신 호환 버전으로 올리고 나머지 lockfile 내용은 그대로 둡니다 [1][2].
1. [2] 이 플래그는 지정한 패키지를 최신 호환 버전으로 올리고 나머지 lockfile 내용은 그대로 둡니다 [1][2].
2. [2] 업그레이드는 프로젝트의 의존성 제약 범위를 넘지 않습니다 [2].
3. [3] **PEP 751 형식으로 내보내기:** `uv export -o pylock.toml` 또는 `uv export --format pylock.toml`을 사용합니다 [3][2].
4. [2] **PEP 751 형식으로 내보내기:** `uv export -o pylock.toml` 또는 `uv export --format pylock.toml`을 사용합니다 [3][2].
5. [3] `-o`로 출력 파일을 지정할 수 있습니다 [3].

**핵심 요점**:

0. Uses `uv lock --upgrade-package requests` to update requests.
1. Exports using `uv export` with `--format pylock.toml`.
2. Uses `--output-file release/pylock.toml` or an equivalent path in the release directory.
3. Places the upgrade before the export.

**금지 내용**:

0. Claims the upgrade updates all packages rather than targeting requests.
1. Exports to stdout while claiming local paths will be relative to the release directory.

<details><summary>근거 문서</summary>

**[1] guides/projects.md**

```text
### `uv.lock`

`uv.lock` is a cross-platform lockfile that contains exact information about your project's
dependencies. Unlike the `pyproject.toml` which is used to specify the broad requirements of your
project, the lockfile contains the exact resolved versions that are installed in the project
environment. This file should be checked into version control, allowing for consistent and
reproducible installations across machines.

`uv.lock` is a human-readable TOML file but is managed by uv and should not be edited manually.

See the [lockfile](../concepts/projects/layout.md#the-lockfile) documentation for more details.

## Managing dependencies

You can add dependencies to your `pyproject.toml` with the `uv add` command. This will also update
the lockfile and project environment:

```console
$ uv add requests
```

You can also specify version constraints or alternative sources:

```console
$ # Specify a version constraint
$ uv add 'requests==2.31.0'

$ # Add a git dependency
$ uv add git+https://github.com/psf/requests
```

If you're migrating from a `requirements.txt` file, you can use `uv add` with the `-r` flag to add
all dependencies from the file:

```console
$ # Add all dependencies from `requirements.txt`.
$ uv add -r requirements.txt -c constraints.txt
```

To remove a package, you can use `uv remove`:

```console
$ uv remove requests
```

To upgrade a package, run `uv lock` with the `--upgrade-package` flag:

```console
$ uv lock --upgrade-package requests
```

The `--upgrade-package` flag will attempt to update the specified package to the latest compatible
version, while keeping the rest of the lockfile intact.

See the documentation on [managing dependencies](../concepts/projects/dependencies.md) for more
details.
```

**[2] concepts/projects/sync.md**

```text
## Upgrading locked package versions

With an existing `uv.lock` file, uv will prefer the previously locked versions of packages when
running `uv sync` and `uv lock`. Package versions will only change if the project's dependency
constraints exclude the previous, locked version.

To upgrade all packages:

```console
$ uv lock --upgrade
```

To upgrade a single package to the latest version, while retaining the locked versions of all other
packages:

```console
$ uv lock --upgrade-package <package>
```

To upgrade a single package to a specific version:

```console
$ uv lock --upgrade-package <package>==<version>
```

In all cases, upgrades are limited to the project's dependency constraints. For example, if the
project defines an upper bound for a package then an upgrade will not go beyond that version.

!!! note

    uv applies similar logic to Git dependencies. For example, if a Git dependency references
    the `main` branch, uv will prefer the locked commit SHA in an existing `uv.lock` file over
    the latest commit on the `main` branch, unless the `--upgrade` or `--upgrade-package` flags
    are used.

These flags can also be provided to `uv sync` or `uv run` to update the lockfile _and_ the
environment.

## Exporting the lockfile

If you need to integrate uv with other tools or workflows, you can export `uv.lock` to different
formats including `requirements.txt`, `pylock.toml` (PEP 751), and CycloneDX SBOM.

```console
$ uv export --format requirements.txt
$ uv export --format pylock.toml
$ uv export --format cyclonedx1.5
```

See the [export guide](./export.md) for comprehensive documentation on all export formats and their
use cases.
```

**[3] concepts/projects/layout.md**

```text
### Relationship to `pylock.toml`

In [PEP 751](https://peps.python.org/pep-0751/), Python standardized a new resolution file format,
`pylock.toml`.

`pylock.toml` is a resolution output format intended to replace `requirements.txt` (e.g., in the
context of `uv pip compile`, whereby a "locked" `requirements.txt` file is generated from a set of
input requirements). `pylock.toml` is standardized and tool-agnostic, such that in the future,
`pylock.toml` files generated by uv could be installed by other tools, and vice versa.

Some of uv's functionality cannot be expressed in the `pylock.toml` format; as such, uv will
continue to use the `uv.lock` format within the project interface.

However, uv supports `pylock.toml` as an export target and in the `uv pip` CLI. For example:

- To export a `uv.lock` to the `pylock.toml` format, run: `uv export -o pylock.toml`
- To generate a `pylock.toml` file from a set of requirements, run:
  `uv pip compile requirements.in -o pylock.toml`
- To install from a `pylock.toml` file, run: `uv pip sync pylock.toml` or
  `uv pip install -r pylock.toml`
```

**[4] concepts/projects/sync.md**

```text
# Locking and syncing

Locking is the process of [resolving](../resolution.md) your project's dependencies into a
[lockfile](./layout.md#the-lockfile). Syncing is the process of installing a subset of packages from
the lockfile into the [project environment](./layout.md#the-project-environment).

## Automatic lock and sync

Locking and syncing are _automatic_ in uv. For example, when `uv run` is used, the project is locked
and synced before invoking the requested command. This ensures the project environment is always
up-to-date. Similarly, commands which read the lockfile, such as `uv tree`, will automatically
update it before running.

To disable automatic locking, use the `--locked` option:

```console
$ uv run --locked ...
```

If the lockfile is not up-to-date, uv will raise an error instead of updating the lockfile.

To use the lockfile without checking if it is up-to-date, use the `--frozen` option:

```console
$ uv run --frozen ...
```

Similarly, to run a command without checking if the environment is up-to-date, use the `--no-sync`
option:

```console
$ uv run --no-sync ...
```

## Checking the lockfile

When considering if the lockfile is up-to-date, uv will check if it matches the project metadata.
For example, if you add a dependency to your `pyproject.toml`, the lockfile will be considered
outdated. Similarly, if you change the version constraints for a dependency such that the locked
version is excluded, the lockfile will be considered outdated. However, if you change the version
constraints such that the existing locked version is still included, the lockfile will still be
considered up-to-date.

You can check if the lockfile is up-to-date by passing the `--check` flag to `uv lock`:

```console
$ uv lock --check
```

This is equivalent to the `--locked` flag for other commands.

!!! important

    uv will not consider lockfiles outdated when new versions of packages are released — the lockfile
    needs to be explicitly updated if you want to upgrade dependencies. See the documentation on
    [upgrading locked package versions](#upgrading-locked-package-versions) for details.
```

**[5] concepts/resolution.md**

```text
## Source distribution

[PEP 625](https://peps.python.org/pep-0625/) specifies that packages must distribute source
distributions as gzip tarball (`.tar.gz`) archives. Prior to this specification, other archive
formats, which need to be supported for backward compatibility, were also allowed.

!!! important

    As of 0.12, uv rejects source distributions that do not conform to
    [PEP 625]'s extension requirements with the exception of `.zip` archives,
    which are still accepted for backward compatibility.

## Lockfile versioning

The `uv.lock` file uses a versioned schema. The schema version is included in the `version` field of
the lockfile.

Any given version of uv can read and write lockfiles with the same schema version, but will reject
lockfiles with a greater schema version. For example, if your uv version supports schema v1,
`uv lock` will error if it encounters an existing lockfile with schema v2.

uv versions that support schema v2 _may_ be able to read lockfiles with schema v1 if the schema
update was backwards-compatible. However, this is not guaranteed, and uv may exit with an error if
it encounters a lockfile with an outdated schema version.

The schema version is considered part of the public API, and so is only bumped in minor releases, as
a breaking change (see [Versioning](../reference/policies/versioning.md)). As such, all uv patch
versions within a given minor uv release are guaranteed to have full lockfile compatibility. In
other words, lockfiles may only be rejected across minor releases.

The `revision` field of the lockfile is used to track backwards compatible changes to the lockfile.
For example, adding a new field to distributions. Changes to the revision will not cause older
versions of uv to error.

## Learn more

For more details about the internals of the resolver, see the
[resolver reference](../reference/internals/resolver.md) documentation.
```

</details>

## 10. `bf871eab-2412-570b-adb3-0f75b8d263c7` (multi_doc, ko)

**질문**: ARM64의 Linux 문제를 재현하는 Docker 환경을 공유하려고 합니다. `FROM --platform=linux/arm64 ghcr.io/astral-sh/uv:0.13.7-debian-slim`만으로 아키텍처를 선택하고 나중에 다시 빌드할 때도 같은 베이스 이미지가 사용되도록 보장할 수 있나요? 안 된다면 무엇을 변경해야 하나요?

**답**:

```text
아니요, 보장할 수 없습니다. `--platform=linux/arm64`는 아키텍처만 고정합니다. 이 옵션은 빌드가 시스템 아키텍처 대신 지정한 플랫폼을 사용하도록 하며, uv는 `linux/amd64`와 `linux/arm64` 이미지를 게시합니다 [1]. 다만 버전 태그는 이미지 내용을 고정하지 못합니다. 문서는 태그가 커밋 SHA에서 이동될 수 있다고 설명합니다 [5].

따라서 태그 대신 SHA256 다이제스트로 베이스 이미지를 고정해야 합니다. 문
```

**인용 판정 대상**(문장, 가리키는 근거 번호):

0. [1] 이 옵션은 빌드가 시스템 아키텍처 대신 지정한 플랫폼을 사용하도록 하며, uv는 `linux/amd64`와 `linux/arm64` 이미지를 게시합니다 [1].
1. [5] 문서는 태그가 커밋 SHA에서 이동될 수 있다고 설명합니다 [5].

**핵심 요점**:

0. Says the platform flag selects Linux ARM64.
1. Says the version tag alone does not guarantee an immutable image because tags can move.
2. Recommends pinning the desired image by SHA256 digest while retaining the platform selection.

**금지 내용**:

0. Claims a specific version tag guarantees the same image in future rebuilds.
1. Claims the platform flag alone pins the image contents.

<details><summary>근거 문서</summary>

**[1] reference/troubleshooting/reproducible-examples.md**

```text
### Docker image

Writing a Docker image is often the best way to share a reproducible example because it is entirely
self-contained. This means that the state from the reproducer's system does not affect the problem.

!!! note

    Using a Docker image is only feasible if the issue is reproducible on Linux. When using macOS,
    first check whether the issue also occurs on Linux. Some bugs are specific to the operating
    system. While using Docker to run Windows containers is feasible, it's not
    commonplace. These sorts of bugs are expected to be reported as a [script](#script) instead.

When writing a Docker MRE with uv, it's best to start with one of
[uv's Docker images](../../guides/integration/docker.md#available-images). When doing so, be sure to
pin to a specific version of uv.

```Dockerfile
FROM ghcr.io/astral-sh/uv:0.13.7-debian-slim
```

While Docker images are isolated from the system, the build will use your system's architecture by
default. When sharing a reproduction, you can explicitly set the platform to ensure a reproducer
gets the expected behavior. uv publishes images for `linux/amd64` (e.g., Intel or AMD) and
`linux/arm64` (e.g., Apple M Series or ARM)

```Dockerfile
FROM --platform=linux/amd64 ghcr.io/astral-sh/uv:0.13.7-debian-slim
```

Docker images are best for reproducing issues that can be constructed with commands, e.g.:

```Dockerfile
FROM --platform=linux/amd64 ghcr.io/astral-sh/uv:0.13.7-debian-slim

RUN uv init /mre
WORKDIR /mre
RUN uv add pydantic
RUN uv sync
RUN uv run -v python -c "import pydantic"
```

However, you can also write files into the image inline:

```Dockerfile
FROM --platform=linux/amd64 ghcr.io/astral-sh/uv:0.13.7-debian-slim
```

**[2] guides/integration/docker.md**

```text
### Available images

The following distroless images are available:

- `ghcr.io/astral-sh/uv:latest`
- `ghcr.io/astral-sh/uv:{major}.{minor}.{patch}`, e.g., `ghcr.io/astral-sh/uv:0.13.7`
- `ghcr.io/astral-sh/uv:{major}.{minor}`, e.g., `ghcr.io/astral-sh/uv:0.13` (the latest patch
  version)

And the following derived images are available:

- Based on `alpine:3.23`:
    - `ghcr.io/astral-sh/uv:alpine`
    - `ghcr.io/astral-sh/uv:alpine3.23`
- Based on `alpine:3.22`:
    - `ghcr.io/astral-sh/uv:alpine3.22`
- Based on `debian:trixie-slim`:
    - `ghcr.io/astral-sh/uv:debian-slim`
    - `ghcr.io/astral-sh/uv:trixie-slim`
- Based on `buildpack-deps:trixie`:
    - `ghcr.io/astral-sh/uv:debian`
    - `ghcr.io/astral-sh/uv:trixie`
- Based on `dhi.io/alpine-base:3.23`:
    - `ghcr.io/astral-sh/uv:alpine-dhi`
    - `ghcr.io/astral-sh/uv:alpine3.23-dhi`
- Based on `dhi.io/debian-base:trixie-debian13`:
    - `ghcr.io/astral-sh/uv:debian-dhi`
    - `ghcr.io/astral-sh/uv:trixie-dhi`
- Based on `dhi/python:3.x`:
    - `ghcr.io/astral-sh/uv:python3.14-dhi`
    - `ghcr.io/astral-sh/uv:python3.13-dhi`
    - `ghcr.io/astral-sh/uv:python3.12-dhi`
    - `ghcr.io/astral-sh/uv:python3.11-dhi`
    - `ghcr.io/astral-sh/uv:python3.10-dhi`
```

**[3] guides/integration/docker.md**

```text
- `ghcr.io/astral-sh/uv:python3.15-trixie-slim`
    - `ghcr.io/astral-sh/uv:python3.14-trixie-slim`
    - `ghcr.io/astral-sh/uv:python3.13-trixie-slim`
    - `ghcr.io/astral-sh/uv:python3.12-trixie-slim`
    - `ghcr.io/astral-sh/uv:python3.11-trixie-slim`

As with the distroless image, each derived image is published with uv version tags as
`ghcr.io/astral-sh/uv:{major}.{minor}.{patch}-{base}` and
`ghcr.io/astral-sh/uv:{major}.{minor}-{base}`, e.g., `ghcr.io/astral-sh/uv:0.13.7-alpine`.

In addition, starting with `0.8` each derived image also sets `UV_TOOL_BIN_DIR` to `/usr/local/bin`
to allow `uv tool install` to work as expected with the default user.

For more details, see the [GitHub Container](https://github.com/astral-sh/uv/pkgs/container/uv)
page.
```

**[4] guides/integration/docker.md**

```text
# Using uv in Docker

## Getting started

!!! tip

    Check out the [`uv-docker-example`](https://github.com/astral-sh/uv-docker-example) project for
    an example of best practices when using uv to build an application in Docker.

uv provides both _distroless_ Docker images, which are useful for
[copying uv binaries](#installing-uv) into your own image builds, and images derived from popular
base images, which are useful for using uv in a container. The distroless images do not contain
anything but the uv binaries. In contrast, the derived images include an operating system with uv
pre-installed.

As an example, to run uv in a container using a Debian-based image:

```console
$ docker run --rm -it ghcr.io/astral-sh/uv:debian uv --help
```
```

**[5] guides/integration/docker.md**

```text
### Installing uv

Use one of the above images with uv pre-installed or install uv by copying the binary from the
official distroless Docker image:

```dockerfile title="Dockerfile"
FROM python:3.12-slim-trixie
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
```

Or, with the installer:

```dockerfile title="Dockerfile"
FROM python:3.12-slim-trixie

# The installer requires curl (and certificates) to download the release archive
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates

# Download the latest installer
ADD https://astral.sh/uv/install.sh /uv-installer.sh

# Run the installer then remove it
RUN sh /uv-installer.sh && rm /uv-installer.sh

# Ensure the installed binary is on the `PATH`
ENV PATH="/root/.local/bin/:$PATH"
```

Note this requires `curl` to be available.

In either case, it is best practice to pin to a specific uv version, e.g., with:

```dockerfile
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /uvx /bin/
```

!!! tip

    While the Dockerfile example above pins to a specific tag, it's also
    possible to pin a specific SHA256. Pinning a specific SHA256 is considered
    best practice in environments that require reproducible builds as tags can
    be moved across different commit SHAs.

    ```Dockerfile
    COPY --from=ghcr.io/astral-sh/uv@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff /uv /uvx /bin/
    ```

Or, with the installer:

```dockerfile
ADD https://astral.sh/uv/0.13.7/install.sh /uv-installer.sh
```
```

</details>

## 11. `16d3354a-5ea1-5271-b39b-893c53fb5872` (summary, en)

**질문**: How does uv's PyTorch backend selection work, and where can I use it?

**답**:

```text
uv's automatic backend selection works by querying the system for the installed CUDA driver, AMD GPU versions, and Intel GPU presence, then using the most-compatible PyTorch index for the relevant packages such as `torch` and `torchvision` [1]. If no such GPU is found, uv falls back to the CPU-only index [1]. Packages outside the PyTorch ecosystem still use your existing index configuration [1].

You enable it with `--torch-backend=auto` or the `UV_TORCH_BACKEND=auto` environment variable [1]. For example: `uv pip install torch --torch-backend=auto` [1]. You can also choose a specific backend, such as CUDA 13.0, with `--torch-backend=cu130` or `UV_TORCH_BACKEND=cu130` [1].

It is only available in the `uv pip` interface [1]. For the project interface (`uv lock`, `uv sync`, `uv run`), the documents instead describe configuring a named PyTorch index with `explicit = true` in `pyproject.toml` and pointing `torch` and `torchvision` to it through `[tool.uv.sources]` [1][3][4]. Some of these features require uv 0.5.3 or later [2].
```

**인용 판정 대상**(문장, 가리키는 근거 번호):

0. [1] uv's automatic backend selection works by querying the system for the installed CUDA driver, AMD GPU versions, and Intel GPU presence, then using the most-compatible PyTorch index for the relevant packages such as `torch` and `torchvision` [1].
1. [1] If no such GPU is found, uv falls back to the CPU-only index [1].
2. [1] Packages outside the PyTorch ecosystem still use your existing index configuration [1].
3. [1] You enable it with `--torch-backend=auto` or the `UV_TORCH_BACKEND=auto` environment variable [1].
4. [1] For example: `uv pip install torch --torch-backend=auto` [1].
5. [1] You can also choose a specific backend, such as CUDA 13.0, with `--torch-backend=cu130` or `UV_TORCH_BACKEND=cu130` [1].
6. [1] It is only available in the `uv pip` interface [1].
7. [1] For the project interface (`uv lock`, `uv sync`, `uv run`), the documents instead describe configuring a named PyTorch index with `explicit = true` in `pyproject.toml` and pointing `torch` and `torchvision` to it through `[tool.uv.sources]` [1][3][4].
8. [3] For the project interface (`uv lock`, `uv sync`, `uv run`), the documents instead describe configuring a named PyTorch index with `explicit = true` in `pyproject.toml` and pointing `torch` and `torchvision` to it through `[tool.uv.sources]` [1][3][4].
9. [4] For the project interface (`uv lock`, `uv sync`, `uv run`), the documents instead describe configuring a named PyTorch index with `explicit = true` in `pyproject.toml` and pointing `torch` and `torchvision` to it through `[tool.uv.sources]` [1][3][4].
10. [2] Some of these features require uv 0.5.3 or later [2].

**핵심 요점**:

0. Identifies the command-line flag or environment variable for automatic selection.
1. Explains GPU detection, compatible index selection, and CPU-only fallback.
2. States that existing index configuration is preserved for packages outside the PyTorch ecosystem.
3. Notes that a specific backend can be selected and that backend selection is currently limited to `uv pip`.

**금지 내용**:

0. Claims automatic selection always uses a GPU index even when no supported GPU is found.
1. Claims `--torch-backend` is currently available in uv's project interface.

<details><summary>근거 문서</summary>

**[1] guides/integration/pytorch.md**

```text
## The `uv pip` interface

While the above examples are focused on uv's project interface (`uv lock`, `uv sync`, `uv run`,
etc.), PyTorch can also be installed via the `uv pip` interface.

PyTorch itself offers a [dedicated interface](https://pytorch.org/get-started/locally/) to determine
the appropriate pip command to run for a given target configuration. For example, you can install
stable, CPU-only PyTorch on Linux with:

```shell
$ pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

To use the same workflow with uv, replace `pip3` with `uv pip`:

```shell
$ uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

## Automatic backend selection

uv supports automatic selection of the appropriate PyTorch index via the `--torch-backend=auto`
command-line argument (or the `UV_TORCH_BACKEND=auto` environment variable), as in:

```shell
$ # With a command-line argument.
$ uv pip install torch --torch-backend=auto

$ # With an environment variable.
$ UV_TORCH_BACKEND=auto uv pip install torch
```

When enabled, uv will query for the installed CUDA driver, AMD GPU versions, and Intel GPU presence,
then use the most-compatible PyTorch index for all relevant packages (e.g., `torch`, `torchvision`,
etc.). If no such GPU is found, uv will fall back to the CPU-only index. uv will continue to respect
existing index configuration for any packages outside the PyTorch ecosystem.

You can also select a specific backend (e.g., CUDA 13.0) with `--torch-backend=cu130` (or
`UV_TORCH_BACKEND=cu130`):

```shell
$ # With a command-line argument.
$ uv pip install torch torchvision --torch-backend=cu130

$ # With an environment variable.
$ UV_TORCH_BACKEND=cu130 uv pip install torch torchvision
```

At present, `--torch-backend` is only available in the `uv pip` interface.
```

**[2] guides/integration/pytorch.md**

```text
# Using uv with PyTorch

The [PyTorch](https://pytorch.org/) ecosystem is a popular choice for deep learning research and
development. You can use uv to manage PyTorch projects and PyTorch dependencies across different
Python versions and environments, even controlling for the choice of accelerator (e.g., CPU-only vs.
CUDA).

!!! note

    Some of the features outlined in this guide require uv version 0.5.3 or later. We recommend upgrading prior to configuring PyTorch.
```

**[3] guides/integration/pytorch.md**

```text
=== "Intel GPUs"

    ```toml
    [[tool.uv.index]]
    name = "pytorch-xpu"
    url = "https://download.pytorch.org/whl/xpu"
    explicit = true
    ```

We recommend the use of `explicit = true` to ensure that the index is _only_ used for `torch`,
`torchvision`, and other PyTorch-related packages, as opposed to generic dependencies like `jinja2`,
which should continue to be sourced from the default index (PyPI).

Next, update the `pyproject.toml` to point `torch` and `torchvision` to the desired index:

=== "CPU-only"

    ```toml
    [tool.uv.sources]
    torch = [
      { index = "pytorch-cpu" },
    ]
    torchvision = [
      { index = "pytorch-cpu" },
    ]
    ```

=== "CUDA 11.8"

    PyTorch doesn't publish CUDA builds for macOS. As such, we gate on `sys_platform` to instruct uv to use
    the PyTorch index on Linux and Windows, but fall back to PyPI on macOS:

    ```toml
    [tool.uv.sources]
    torch = [
      { index = "pytorch-cu118", marker = "sys_platform == 'linux' or sys_platform == 'win32'" },
    ]
    torchvision = [
      { index = "pytorch-cu118", marker = "sys_platform == 'linux' or sys_platform == 'win32'" },
    ]
    ```

=== "CUDA 12.6"

    PyTorch doesn't publish CUDA builds for macOS. As such, we gate on `sys_platform` to instruct uv to limit
    the PyTorch index to Linux and Windows, falling back to PyPI on macOS:

    ```toml
    [tool.uv.sources]
    torch = [
      { index = "pytorch-cu126", marker = "sys_platform == 'linux' or sys_platform == 'win32'" },
    ]
    torchvision = [
      { index = "pytorch-cu126", marker = "sys_platform == 'linux' or sys_platform == 'win32'" },
    ]
    ```

=== "CUDA 12.8"
```

**[4] guides/integration/pytorch.md**

```text
=== "CUDA 12.8"

    PyTorch doesn't publish CUDA builds for macOS. As such, we gate on `sys_platform` to instruct uv to limit
    the PyTorch index to Linux and Windows, falling back to PyPI on macOS:

    ```toml
    [tool.uv.sources]
    torch = [
      { index = "pytorch-cu128", marker = "sys_platform == 'linux' or sys_platform == 'win32'" },
    ]
    torchvision = [
      { index = "pytorch-cu128", marker = "sys_platform == 'linux' or sys_platform == 'win32'" },
    ]
    ```

=== "CUDA 13.0"

    PyTorch doesn't publish CUDA builds for macOS. As such, we gate on `sys_platform` to instruct uv to limit
    the PyTorch index to Linux and Windows, falling back to PyPI on macOS:

    ```toml
    [tool.uv.sources]
    torch = [
      { index = "pytorch-cu130", marker = "sys_platform == 'linux' or sys_platform == 'win32'" },
    ]
    torchvision = [
      { index = "pytorch-cu130", marker = "sys_platform == 'linux' or sys_platform == 'win32'" },
    ]
    ```

=== "ROCm 7.2"

    PyTorch doesn't publish ROCm builds for macOS or Windows. As such, we gate on `sys_platform` to instruct uv
    to limit the PyTorch index to Linux, falling back to PyPI on macOS and Windows:
```

**[5] concepts/build-backend.md**

```text
# The uv build backend

A build backend transforms a source tree (i.e., a directory) into a source distribution or a wheel.

uv supports all build backends (as specified by [PEP 517](https://peps.python.org/pep-0517/)), but
also provides a native build backend (`uv_build`) that integrates tightly with uv to improve
performance and user experience.

## Choosing a build backend

The uv build backend is a great choice for most Python projects. It has reasonable defaults, with
the goal of requiring zero configuration for most users, but provides flexible configuration to
accommodate most Python project structures. It integrates tightly with uv, to improve messaging and
user experience. It validates project metadata and structures, preventing common mistakes. And,
finally, it's very fast.

The uv build backend currently **only supports pure Python code**. An alternative backend is
required to build a
[library with extension modules](../concepts/projects/init.md#projects-with-extension-modules).

!!! tip

    While the backend supports a number of options for configuring your project structure, when build scripts or
    a more flexible project layout are required, consider using the
    [hatchling](https://hatch.pypa.io/latest/config/build/#build-system) build backend instead.

## Using the uv build backend

To use uv as a build backend in an existing project, add `uv_build` to the
[`[build-system]`](../concepts/projects/config.md#build-systems) section in your `pyproject.toml`:

```toml title="pyproject.toml"
[build-system]
requires = ["uv_build>=0.13.7,<0.14"]
build-backend = "uv_build"
```

!!! note

    The uv build backend follows the same [versioning policy](../reference/policies/versioning.md)
    as uv. Including an upper bound on the `uv_build` version ensures that your package continues to
    build correctly as new versions are released.

To create a new project that uses the uv build backend, use `uv init`:

```console
$ uv init
```

When the project is built, e.g., with [`uv build`](../guides/package.md), the uv build backend will
be used to create the source distribution and wheel.
```

</details>

## 12. `9b225a5c-b6d8-57ad-a055-5805c425ac2b` (summary, en)

**질문**: How does upgrading uv-managed Python versions work, and what are its limits?

**답**:

```text
uv can upgrade uv-managed Python versions to the latest patch release, but only within the same minor version. Upgrades are only supported for uv-managed Python versions [1]. They are not currently supported for PyPy, GraalPy, and Pyodide [1].

To upgrade one version, run `uv python upgrade 3.12`. To upgrade all installed versions, run `uv python upgrade` [1]. The guide also describes upgrading all uv-managed Python versions with this command [3].

After an upgrade, uv prefers the new version but keeps the existing one, because virtual environments may still use it [1]. Virtual environments that use the Python version are automatically upgraded to the new patch version [1]. Environments created with an explicitly requested patch version, such as `uv venv -p 3.10.8`, are not transparently upgraded [1].

The automatic upgrade works through a minor-version directory, such as `~/.local/share/uv/python/cpython-3.12-macos-aarch64-none`. This directory is a symbolic link on Unix or a junction on Windows that points to a specific patch version [1]. If another tool resolves this link, for example by canonicalizing the interpreter path, and uses it to create a virtual environment, that environment will not be upgraded automatically [1].

The main limits are:
- uv does not transparently upgrade across minor versions, such as 3.12 to 3.13, because changing minor versions can affect dependency resolution [1].
- Upgrades do not apply to PyPy, GraalPy, or Pyodide [1].
- Environments pinned to an explicit patch version are not transparently upgraded [1].
- Environments created through resolved paths outside uv's link are not automatically upgraded [1].
```

**인용 판정 대상**(문장, 가리키는 근거 번호):

0. [1] Upgrades are only supported for uv-managed Python versions [1].
1. [1] They are not currently supported for PyPy, GraalPy, and Pyodide [1].
2. [1] To upgrade all installed versions, run `uv python upgrade` [1].
3. [3] The guide also describes upgrading all uv-managed Python versions with this command [3].
4. [1] After an upgrade, uv prefers the new version but keeps the existing one, because virtual environments may still use it [1].
5. [1] Virtual environments that use the Python version are automatically upgraded to the new patch version [1].
6. [1] Environments created with an explicitly requested patch version, such as `uv venv -p 3.10.8`, are not transparently upgraded [1].
7. [1] This directory is a symbolic link on Unix or a junction on Windows that points to a specific patch version [1].
8. [1] If another tool resolves this link, for example by canonicalizing the interpreter path, and uses it to create a virtual environment, that environment will not be upgraded automatically [1].
9. [1] - uv does not transparently upgrade across minor versions, such as 3.12 to 3.13, because changing minor versions can affect dependency resolution [1].
10. [1] - Upgrades do not apply to PyPy, GraalPy, or Pyodide [1].
11. [1] - Environments pinned to an explicit patch version are not transparently upgraded [1].
12. [1] - Environments created through resolved paths outside uv's link are not automatically upgraded [1].

**핵심 요점**:

0. States that only uv-managed Python versions can be upgraded.
1. States that upgrades go to the latest patch release and not across minor versions.
2. Gives `uv python upgrade` (for one version or all) as the command.
3. States that the previous version is retained and the new one is preferred.
4. States that virtual environments are upgraded automatically, except ones created with an explicit patch version.

**금지 내용**:

0. Claims uv upgrades across minor versions, e.g. 3.12 to 3.13.
1. Claims the previous patch version is removed after an upgrade.
2. Claims PyPy, GraalPy or Pyodide versions can be upgraded the same way.

<details><summary>근거 문서</summary>

**[1] concepts/python-versions.md**

```text
## Upgrading Python versions

!!! important

    Upgrades are only supported for uv-managed Python versions.

    Upgrades are not currently supported for PyPy, GraalPy, and Pyodide.

uv allows transparently upgrading Python versions to the latest patch release, e.g., 3.13.4 to
3.13.5. uv does not allow transparently upgrading across minor Python versions, e.g., 3.12 to 3.13,
because changing minor versions can affect dependency resolution.

uv-managed Python versions can be upgraded to the latest supported patch release with the
`python upgrade` command:

To upgrade a Python version to the latest supported patch release:

```console
$ uv python upgrade 3.12
```

To upgrade all installed Python versions:

```console
$ uv python upgrade
```

After an upgrade, uv will prefer the new version, but will retain the existing version as it may
still be used by virtual environments.

Virtual environments using the Python version will be automatically upgraded to the new patch
version.

If a virtual environment was created with an explicitly requested patch version, e.g.,
`uv venv -p 3.10.8`, it will not be transparently upgraded to a new version.

### Minor version directories

Automatic upgrades for virtual environments are implemented using a directory with the Python minor
version, e.g.:

```
~/.local/share/uv/python/cpython-3.12-macos-aarch64-none
```

which is a symbolic link (on Unix) or junction (on Windows) pointing to a specific patch version:

```console
$ readlink ~/.local/share/uv/python/cpython-3.12-macos-aarch64-none
~/.local/share/uv/python/cpython-3.12.11-macos-aarch64-none
```

If this link is resolved by another tool, e.g., by canonicalizing the Python interpreter path, and
used to create a virtual environment, it will not be automatically upgraded.

## Project Python versions

uv will respect Python requirements defined in `requires-python` in the `pyproject.toml` file during
project command invocations. The first Python version that is compatible with the requirement will
be used, unless a version is otherwise requested, e.g., via a `.python-version` file or the
`--python` flag.
```

**[2] guides/install-python.md**

```text
# Installing Python

If Python is already installed on your system, uv will
[detect and use](#using-existing-python-versions) it without configuration. However, uv can also
install and manage Python versions. uv [automatically installs](#automatic-python-downloads) missing
Python versions as needed — you don't need to install Python to get started.

## Getting started

To install the latest Python version:

```console
$ uv python install
```

!!! note

    Python does not publish official distributable binaries. As such, uv uses distributions from the Astral [`python-build-standalone`](https://github.com/astral-sh/python-build-standalone) project. See the [Python distributions](../concepts/python-versions.md#managed-python-distributions) documentation for more details.

Once Python is installed, it will be used by `uv` commands automatically. uv also adds the installed
version to your `PATH`:

```console
$ python3.15
```

uv only installs a _versioned_ executable by default. To install `python` and `python3` executables,
include the experimental `--default` option:

```console
$ uv python install --default
```

!!! tip

    See the documentation on [installing Python executables](../concepts/python-versions.md#installing-python-executables)
    for more details.

## Installing a specific version

To install a specific Python version:

```console
$ uv python install 3.12
```

To install multiple Python versions:

```console
$ uv python install 3.11 3.12
```

To install an alternative Python implementation, e.g., PyPy:

```console
$ uv python install pypy@3.10
```

See the [`python install`](../concepts/python-versions.md#installing-a-python-version) documentation
for more details.

## Reinstalling Python

To reinstall uv-managed Python versions, use `--reinstall`, e.g.:

```console
$ uv python install --reinstall
```

This will reinstall all previously installed Python versions. Improvements are constantly being
added to the Python distributions, so reinstalling may resolve bugs even if the Python version does
not change.
```

**[3] guides/install-python.md**

```text
## Viewing Python installations

To view available and installed Python versions:

```console
$ uv python list
```

See the [`python list`](../concepts/python-versions.md#viewing-available-python-versions)
documentation for more details.

## Automatic Python downloads

Python does not need to be explicitly installed to use uv. By default, uv will automatically
download Python versions when they are required. For example, the following would download Python
3.12 if it was not installed:

```console
$ uvx python@3.12 -c "print('hello world')"
```

Even if a specific Python version is not requested, uv will download the latest version on demand.
For example, if there are no Python versions on your system, the following will install Python
before creating a new virtual environment:

```console
$ uv venv
```

!!! tip

    Automatic Python downloads can be [easily disabled](../concepts/python-versions.md#disabling-automatic-python-downloads) if you want more control over when Python is downloaded.

## Using existing Python versions

uv will use existing Python installations if present on your system. There is no configuration
necessary for this behavior: uv will use the system Python if it satisfies the requirements of the
command invocation. See the
[Python discovery](../concepts/python-versions.md#discovery-of-python-versions) documentation for
details.

To force uv to use the system Python, provide the `--no-managed-python` flag. See the
[Python version preference](../concepts/python-versions.md#requiring-or-disabling-managed-python-versions)
documentation for more details.

## Upgrading Python versions

To upgrade a Python version to the latest supported patch release:

```console
$ uv python upgrade 3.12
```

To upgrade all uv-managed Python versions:

```console
$ uv python upgrade
```

See the [`python upgrade`](../concepts/python-versions.md#upgrading-python-versions) documentation
for more details.

## Next steps

To learn more about `uv python`, see the [Python version concept](../concepts/python-versions.md)
page and the [command reference](../reference/cli.md#uv-python).

Or, read on to learn how to [run scripts](./scripts.md) and invoke Python with uv.
```

**[4] concepts/python-versions.md**

```text
## Installing a Python version

uv bundles a list of downloadable CPython and PyPy distributions for macOS, Linux, and Windows.

!!! tip

    By default, Python versions are automatically downloaded as needed without using
    `uv python install`.

To install a Python version at a specific version:

```console
$ uv python install 3.12.3
```

To install the latest patch version:

```console
$ uv python install 3.12
```

To install a version that satisfies constraints:

```console
$ uv python install '>=3.8,<3.10'
```

To install multiple versions:

```console
$ uv python install 3.9 3.10 3.11
```

To install a specific implementation:

```console
$ uv python install pypy
```

All the [Python version request](#requesting-a-version) formats are supported except those that are
used for requesting local interpreters such as a file path.

By default `uv python install` will verify that a managed Python version is installed or install the
latest version. If a `.python-version` file is present, uv will install the Python version listed in
the file. A project that requires multiple Python versions may define a `.python-versions` file. If
present, uv will install all the Python versions listed in the file.

!!! important

    The available Python versions are frozen for each uv release. To install new Python versions,
    you may need to upgrade uv.

See the [storage documentation](../reference/storage.md#python-versions) for details about where
installed Python versions are stored.
```

**[5] index.md**

```text
## Python versions

uv installs Python and allows quickly switching between versions.

Install multiple Python versions:

```console
$ uv python install 3.10 3.11 3.12
Searching for Python versions matching: Python 3.10
Searching for Python versions matching: Python 3.11
Searching for Python versions matching: Python 3.12
Installed 3 versions in 3.42s
 + cpython-3.10.14-macos-aarch64-none
 + cpython-3.11.9-macos-aarch64-none
 + cpython-3.12.4-macos-aarch64-none
```

Download Python versions as needed:

```console
$ uv venv --python 3.12.0
Using CPython 3.12.0
Creating virtual environment at: .venv
Activate with: source .venv/bin/activate

$ uv run --python pypy@3.8 -- python
Python 3.8.16 (a9dbdca6fc3286b0addd2240f11d97d8e8de187a, Dec 29 2022, 11:45:30)
[PyPy 7.3.11 with GCC Apple LLVM 13.1.6 (clang-1316.0.21.2.5)] on darwin
Type "help", "copyright", "credits" or "license" for more information.
>>>>
```

Use a specific Python version in the current directory:

```console
$ uv python pin 3.11
Pinned `.python-version` to `3.11`
```

See the [installing Python guide](./guides/install-python.md) to get started.
```

</details>

## 13. `bd3f7c9b-f941-558a-ac4d-d146090a20aa` (summary, en)

**질문**: How does publishing a Python package with uv work, including authentication, custom indexes, retries, and attestations?

**답**:

```text
## Publishing with `uv publish`

You publish a package by running `uv publish` [3]. Before publishing, you can check the package with `uv run --with <PACKAGE> --no-project -- python -c "import <PACKAGE>"`, where `--no-project` avoids installing the package from your local project directory [1].

## Authentication

You can set a PyPI token with `--token` or `UV_PUBLISH_TOKEN` [3]. Alternatively, you can set a username with `--username` or `UV_PUBLISH_USERNAME` and a password with `--password` or `UV_PUBLISH_PASSWORD` [3]. PyPI no longer supports publishing with a username and password, so you need a token. Using a token is equivalent to setting `--username __token__` and using the token as the password [3].

For PyPI publishing from GitHub Actions or another Trusted Publisher, you don't need to set credentials. Instead, you add a trusted publisher to the PyPI project [3]. With trusted publishing, uv attempts to invalidate the short-lived PyPI token after publishing, even if publishing fails [3]. If invalidation fails, uv emits a warning without changing the publishing result [3]. Tokens provided explicitly with `--token` or `UV_PUBLISH_TOKEN` are not revoked [3].

## Custom indexes

For a custom index defined through `[[tool.uv.index]]`, you add `publish-url` and use `uv publish --index <name>` [3]. For example, the index can set `name = "testpypi"`, `url = "https://test.pypi.org/simple/"`, `publish-url = "https://test.pypi.org/legacy/"`, and `explicit = true` [3]. When using `--index`, the `pyproject.toml` must be present, so a publish CI job needs a checkout step [3][2].

For Google Artifact Registry, you set `publish-url` on the index and set `UV_PUBLISH_USERNAME=oauth2accesstoken` and `UV_PUBLISH_PASSWORD` to your registry token if you're not using keyring [5]. You can instead set `UV_PUBLISH_URL` to publish without adding `publish-url` to the project, but this is not preferable because uv cannot check whether the package is already published before uploading [5].

## Retries and partial failures

`uv publish` retries failed uploads [2]. If publishing fails partway through, with some files uploaded and others missing, PyPI lets you rerun the exact same command, and existing identical files are ignored [2]
```

**인용 판정 대상**(문장, 가리키는 근거 번호):

0. [3] You publish a package by running `uv publish` [3].
1. [1] Before publishing, you can check the package with `uv run --with <PACKAGE> --no-project -- python -c "import <PACKAGE>"`, where `--no-project` avoids installing the package from your local project directory [1].
2. [3] You can set a PyPI token with `--token` or `UV_PUBLISH_TOKEN` [3].
3. [3] Alternatively, you can set a username with `--username` or `UV_PUBLISH_USERNAME` and a password with `--password` or `UV_PUBLISH_PASSWORD` [3].
4. [3] Using a token is equivalent to setting `--username __token__` and using the token as the password [3].
5. [3] Instead, you add a trusted publisher to the PyPI project [3].
6. [3] With trusted publishing, uv attempts to invalidate the short-lived PyPI token after publishing, even if publishing fails [3].
7. [3] If invalidation fails, uv emits a warning without changing the publishing result [3].
8. [3] Tokens provided explicitly with `--token` or `UV_PUBLISH_TOKEN` are not revoked [3].
9. [3] For a custom index defined through `[[tool.uv.index]]`, you add `publish-url` and use `uv publish --index <name>` [3].
10. [3] For example, the index can set `name = "testpypi"`, `url = "https://test.pypi.org/simple/"`, `publish-url = "https://test.pypi.org/legacy/"`, and `explicit = true` [3].
11. [3] When using `--index`, the `pyproject.toml` must be present, so a publish CI job needs a checkout step [3][2].
12. [2] When using `--index`, the `pyproject.toml` must be present, so a publish CI job needs a checkout step [3][2].
13. [5] For Google Artifact Registry, you set `publish-url` on the index and set `UV_PUBLISH_USERNAME=oauth2accesstoken` and `UV_PUBLISH_PASSWORD` to your registry token if you're not using keyring [5].
14. [5] You can instead set `UV_PUBLISH_URL` to publish without adding `publish-url` to the project, but this is not preferable because uv cannot check whether the package is already published before uploading [5].
15. [2] `uv publish` retries failed uploads [2].
16. [2] If publishing fails partway through, with some files uploaded and others missing, PyPI lets you rerun the exact same command, and existing identical files are ignored [2]

**핵심 요점**:

0. Identifies `uv publish` as the publishing command and describes PyPI token or trusted-publisher authentication.
1. Explains that a custom index needs `publish-url` and `uv publish --index <name>`.
2. Explains how to retry a partial PyPI upload and use `--check-url` with other registries.
3. States that uv discovers and uploads matching attestations to supported registries.

**금지 내용**:

0. Claims PyPI accepts ordinary username-and-password publishing.
1. Claims uv generates attestations during publishing.
2. Says `--check-url` should point to the publishing URL rather than the index URL.

<details><summary>근거 문서</summary>

**[1] guides/package.md**

```text
### Uploading attestations with your package

!!! note

    Some third-party package indexes may not support attestations, and may
    reject uploads that include them (rather than silently ignoring them).
    If you encounter issues when uploading, you can use `--no-attestations` or
    `UV_PUBLISH_NO_ATTESTATIONS` to disable uv's default behavior.

!!! tip

    `uv publish` does not currently generate attestations; attestations must
    be created separately before publishing.

`uv publish` supports uploading [attestations](https://peps.python.org/pep-0740/) to registries that
support them, like PyPI.

uv will automatically discover and match attestations. For example, given the following `dist/`
directory, `uv publish` will upload the attestations along with their corresponding distributions:

```console
$ ls dist/
hello_world-1.0.0-py3-none-any.whl
hello_world-1.0.0-py3-none-any.whl.publish.attestation
hello_world-1.0.0.tar.gz
hello_world-1.0.0.tar.gz.publish.attestation
```

## Installing your package

Test that the package can be installed and imported with `uv run`:

```console
$ uv run --with <PACKAGE> --no-project -- python -c "import <PACKAGE>"
```

The `--no-project` flag is used to avoid installing the package from your local project directory.

!!! tip

    If you have recently installed the package, you may need to include the
    `--refresh-package <PACKAGE>` option to avoid using a cached version of the package.

## Next steps

To learn more about publishing packages, check out the
[PyPA guides](https://packaging.python.org/en/latest/guides/section-build-and-publish/) on building
and publishing.

Or, read on for [guides](./integration/index.md) on integrating uv with other software.
```

**[2] guides/package.md**

```text
!!! note

    When using `uv publish --index <name>`, the `pyproject.toml` must be present, i.e., you need to
    have a checkout step in a publish CI job.

Even though `uv publish` retries failed uploads, it can happen that publishing fails in the middle,
with some files uploaded and some files still missing. With PyPI, you can retry the exact same
command; existing identical files will be ignored. With other registries, use
`--check-url <index url>` with the index URL (not the publishing URL) the packages belong to. When
using `--index`, the index URL is used as check URL. uv will skip uploading files that are identical
to files in the registry, and it will also handle raced parallel uploads. Note that existing files
need to match exactly with those previously uploaded to the registry. This avoids accidentally
publishing source distribution and wheels with different contents for the same version.
```

**[3] guides/package.md**

```text
## Publishing your package

!!! note

    A complete guide to publishing from GitHub Actions to PyPI can be found in the
    [GitHub Guide](integration/github.md#publishing-to-pypi)

Publish your package with `uv publish`:

```console
$ uv publish
```

Set a PyPI token with `--token` or `UV_PUBLISH_TOKEN`, or set a username with `--username` or
`UV_PUBLISH_USERNAME` and password with `--password` or `UV_PUBLISH_PASSWORD`. For publishing to
PyPI from GitHub Actions or another Trusted Publisher, you don't need to set any credentials.
Instead,
[add a trusted publisher to the PyPI project](https://docs.pypi.org/trusted-publishers/adding-a-publisher/).

When using trusted publishing, uv will attempt to invalidate the short-lived PyPI token after
publishing, even if publishing fails. This further reduces the exposure period for the short-lived
token, beyond its already short lifetime.

If invalidation fails, uv emits a warning without changing the publishing result. Tokens provided
explicitly with `--token` or `UV_PUBLISH_TOKEN` are not revoked.

!!! note

    PyPI does not support publishing with username and password anymore, instead you need to
    generate a token. Using a token is equivalent to setting `--username __token__` and using the
    token as password.

If you're using a custom index through `[[tool.uv.index]]`, add `publish-url` and use
`uv publish --index <name>`. For example:

```toml
[[tool.uv.index]]
name = "testpypi"
url = "https://test.pypi.org/simple/"
publish-url = "https://test.pypi.org/legacy/"
explicit = true
```

!!! note

    When using `uv publish --index <name>`, the `pyproject.toml` must be present, i.e., you need to
    have a checkout step in a publish CI job.
```

**[4] concepts/authentication/index.md**

```text
# Authentication

Authentication is required when working with private repositories or package indexes.

Learn more about authentication in uv:

- [Using the `uv auth` CLI](./cli.md)
- [HTTP authentication](./http.md)
- [Git authentication](./git.md)
- [TLS certificates](./certificates.md)
- [Third-party services](./third-party.md)
```

**[5] guides/integration/google.md**

```text
## Publishing packages

If you also want to publish your own packages to Google Artifact Registry, you can use `uv publish`
as described in the [Building and publishing guide](../package.md).

First, add a `publish-url` to the index you want to publish packages to. For example:

```toml title="pyproject.toml" hl_lines="4"
[[tool.uv.index]]
name = "private-registry"
url = "https://<REGION>-python.pkg.dev/<PROJECT>/<REPOSITORY>/simple/"
publish-url = "https://<REGION>-python.pkg.dev/<PROJECT>/<REPOSITORY>/"
```

Then, configure credentials (if not using keyring):

```console
$ export UV_PUBLISH_USERNAME=oauth2accesstoken
$ export UV_PUBLISH_PASSWORD="$ARTIFACT_REGISTRY_TOKEN"
```

And publish the package:

```console
$ uv publish --index private-registry
```

To use `uv publish` without adding the `publish-url` to the project, you can set `UV_PUBLISH_URL`:

```console
$ export UV_PUBLISH_URL=https://<REGION>-python.pkg.dev/<PROJECT>/<REPOSITORY>/
$ uv publish
```

Note this method is not preferable because uv cannot check if the package is already published
before uploading artifacts.
```

</details>

## 14. `ae7bab45-7ea5-5b5a-aefe-6d706f178ff0` (summary, ko)

**질문**: uv는 개발 의존성 그룹을 어떻게 처리하나요? 게시, 그룹 추가, 의존성 해석, 기본 포함 여부도 포함해서 설명해 주세요.

**답**:

```text
uv는 개발 의존성을 `[dependency-groups]` 테이블에 선언하며, 이 테이블은 PEP 735를 따릅니다 [2][4].

**게시 시 처리**
개발 의존성은 로컬 전용이므로 PyPI나 다른 인덱스에 게시할 때 프로젝트 요구사항에 포함되지 않습니다 [4]. 따라서 `[project]` 테이블에도 들어가지 않습니다 [4]. 개발 의존성도 일반 의존성과 마찬가지로 `tool.uv.sources` 항목을 가질 수 있습니다 [4].

**그룹 추가**
`--dev` 플래그로 개발 의존성을 추가합니다. 예를 들어 `uv add --dev pytest`를 실행하면 `dev` 그룹이 생성됩니다 [4]. 임의의 그룹 이름도 지원됩니다. `uv add --group lint ruff`를 실행하면 `lint` 그룹이 만들어집니다 [1]. 문서 가져오기에서도 `uv add -r requirements-docs.in -c requirements-docs.txt --group docs`처럼 `--group`으로 그룹을 지정할 수 있습니다 [5]. 그룹은 다른 그룹을 `{include-group = "..."}` 형태로 포함할 수 있습니다 [1]. 다만 포함되는 그룹의 의존성은 다른 그룹에 선언된 의존성과 충돌할 수 없습니다 [1].

**의존성 해석**
uv는 모든 의존성 그룹이 서로 호환되어야 하며, 잠금 파일을 만들 때 모든 그룹을 함께 해석합니다 [1]. 한 그룹의 의존성이 다른 그룹과 호환되지 않으면 해석이 오류와 함께 실패합니다 [1]. 서로 충돌하는 그룹이 있다면, [충돌 의존성으로 명시적으로 선언](./config.md#conflicting-dependencies)하지 않는 한 해석이 실패합니다 [1].

**기본 포함 여부**
uv는 기본적으로 `uv run`이나 `uv sync` 중에 `dev` 그룹을 환경에 포함합니다 [3]. `tool.uv.default-groups` 설정으로 기본 그룹을 바꿀 수 있고 [3], `"all"`을 지정하면 모든 그룹을 기본으로 활성화합니다 [3]. `--no-default-groups`로 기본 그룹 전체를 끌 수 있으며, `--no-group <name>`으로 특정 기본 그룹만 제외할 수 있습니다 [3]. `--no-dev`로 `dev` 그룹을 제외하고 [2], `--only-dev`로 프로젝트와 그 의존성 없이 `dev` 그룹만 설치할 수 있습니
```

**인용 판정 대상**(문장, 가리키는 근거 번호):

0. [2] uv는 개발 의존성을 `[dependency-groups]` 테이블에 선언하며, 이 테이블은 PEP 735를 따릅니다 [2][4].
1. [4] uv는 개발 의존성을 `[dependency-groups]` 테이블에 선언하며, 이 테이블은 PEP 735를 따릅니다 [2][4].
2. [4] 개발 의존성은 로컬 전용이므로 PyPI나 다른 인덱스에 게시할 때 프로젝트 요구사항에 포함되지 않습니다 [4].
3. [4] 따라서 `[project]` 테이블에도 들어가지 않습니다 [4].
4. [4] 개발 의존성도 일반 의존성과 마찬가지로 `tool.uv.sources` 항목을 가질 수 있습니다 [4].
5. [4] 예를 들어 `uv add --dev pytest`를 실행하면 `dev` 그룹이 생성됩니다 [4].
6. [1] `uv add --group lint ruff`를 실행하면 `lint` 그룹이 만들어집니다 [1].
7. [5] 문서 가져오기에서도 `uv add -r requirements-docs.in -c requirements-docs.txt --group docs`처럼 `--group`으로 그룹을 지정할 수 있습니다 [5].
8. [1] 그룹은 다른 그룹을 `{include-group = "..."}` 형태로 포함할 수 있습니다 [1].
9. [1] 다만 포함되는 그룹의 의존성은 다른 그룹에 선언된 의존성과 충돌할 수 없습니다 [1].
10. [1] uv는 모든 의존성 그룹이 서로 호환되어야 하며, 잠금 파일을 만들 때 모든 그룹을 함께 해석합니다 [1].
11. [1] 한 그룹의 의존성이 다른 그룹과 호환되지 않으면 해석이 오류와 함께 실패합니다 [1].
12. [1] 서로 충돌하는 그룹이 있다면, [충돌 의존성으로 명시적으로 선언](./config.md#conflicting-dependencies)하지 않는 한 해석이 실패합니다 [1].
13. [3] uv는 기본적으로 `uv run`이나 `uv sync` 중에 `dev` 그룹을 환경에 포함합니다 [3].
14. [3] `tool.uv.default-groups` 설정으로 기본 그룹을 바꿀 수 있고 [3], `"all"`을 지정하면 모든 그룹을 기본으로 활성화합니다 [3].
15. [3] `--no-default-groups`로 기본 그룹 전체를 끌 수 있으며, `--no-group <name>`으로 특정 기본 그룹만 제외할 수 있습니다 [3].
16. [2] `--no-dev`로 `dev` 그룹을 제외하고 [2], `--only-dev`로 프로젝트와 그 의존성 없이 `dev` 그룹만 설치할 수 있습니

**핵심 요점**:

0. States that development dependencies are local-only, not published requirements, and are declared in dependency groups.
1. Explains how to add dependencies to the dev group and to another named group.
2. States that all groups are resolved together and must be compatible unless conflicts are explicitly declared.
3. States that dev is included by default and the default groups are configurable.

**금지 내용**:

0. Claims development dependency groups are published as project requirements.
1. Claims uv resolves each dependency group independently.

<details><summary>근거 문서</summary>

**[1] concepts/projects/dependencies.md**

```text
### Dependency groups

Development dependencies can be divided into multiple groups, using the `--group` flag.

For example, to add a development dependency in the `lint` group:

```console
$ uv add --group lint ruff
```

Which results in the following `[dependency-groups]` definition:

```toml title="pyproject.toml"
[dependency-groups]
dev = [
  "pytest"
]
lint = [
  "ruff"
]
```

Once groups are defined, the `--all-groups`, `--no-default-groups`, `--group`, `--only-group`, and
`--no-group` options can be used to include or exclude their dependencies.

!!! tip

    The `--dev`, `--only-dev`, and `--no-dev` flags are equivalent to `--group dev`,
    `--only-group dev`, and `--no-group dev` respectively.

uv requires that all dependency groups are compatible with each other and resolves all groups
together when creating the lockfile.

If dependencies declared in one group are not compatible with those in another group, uv will fail
to resolve the requirements of the project with an error.

!!! note

    If you have dependency groups that conflict with one another, resolution will fail
    unless you explicitly [declare them as conflicting](./config.md#conflicting-dependencies).

### Nesting groups

A dependency group can include other dependency groups, e.g.:

```toml title="pyproject.toml"
[dependency-groups]
dev = [
  {include-group = "lint"},
  {include-group = "test"}
]
lint = [
  "ruff"
]
test = [
  "pytest"
]
```

An included group's dependencies cannot conflict with the other dependencies declared in a group.
```

**[2] concepts/projects/sync.md**

```text
### Syncing development dependencies

uv reads development dependencies from the `[dependency-groups]` table (as defined in
[PEP 735](https://peps.python.org/pep-0735/)).

The `dev` group is special-cased and synced by default. See the
[default groups](./dependencies.md#default-groups) documentation for details on changing the
defaults.

The `--no-dev` flag can be used to exclude the `dev` group.

The `--only-dev` flag can be used to install the `dev` group _without_ the project and its
dependencies.

Additional groups can be included or excluded with the `--all-groups`, `--no-default-groups`,
`--group <name>`, `--only-group <name>`, and `--no-group <name>` options. The semantics of
`--only-group` are the same as `--only-dev`: the project will not be included. However,
`--only-group` will also exclude default groups.

Group exclusions always take precedence over inclusions, so given the command:

```
$ uv sync --no-group foo --group foo
```

The `foo` group would not be installed.

See the [development dependencies](./dependencies.md#development-dependencies) documentation for
details on how to manage development dependencies.
```

**[3] concepts/projects/dependencies.md**

```text
### Default groups

By default, uv includes the `dev` dependency group in the environment (e.g., during `uv run` or
`uv sync`). The default groups to include can be changed using the `tool.uv.default-groups` setting.

```toml title="pyproject.toml"
[tool.uv]
default-groups = ["dev", "foo"]
```

To enable all dependency groups by default, use `"all"` instead of listing group names:

```toml title="pyproject.toml"
[tool.uv]
default-groups = "all"
```

!!! tip

    To disable this behaviour during `uv run` or `uv sync`, use `--no-default-groups`.
    To exclude a specific default group, use `--no-group <name>`.

### Group `requires-python`

By default, dependency groups must be compatible with your project's `requires-python` range.

If a dependency group requires a different range of Python versions than your project, you can
specify a `requires-python` for the group in `[tool.uv.dependency-groups]`, e.g.:

```toml title="pyproject.toml" hl_lines="9-10"
[project]
name = "example"
version = "0.0.0"
requires-python = ">=3.10"

[dependency-groups]
dev = ["pytest"]

[tool.uv.dependency-groups]
dev = {requires-python = ">=3.12"}
```

### Legacy `dev-dependencies`

Before `[dependency-groups]` was standardized, uv used the `tool.uv.dev-dependencies` field to
specify development dependencies, e.g.:

```toml title="pyproject.toml"
[tool.uv]
dev-dependencies = [
  "pytest"
]
```

Dependencies declared in this section will be combined with the contents in the
`dependency-groups.dev`. Eventually, the `dev-dependencies` field will be deprecated and removed.

!!! note

    If a `tool.uv.dev-dependencies` field exists, `uv add --dev` will use the existing section
    instead of adding a new `dependency-groups.dev` section.
```

**[4] concepts/projects/dependencies.md**

```text
## Development dependencies

Unlike optional dependencies, development dependencies are local-only and will _not_ be included in
the project requirements when published to PyPI or other indexes. As such, development dependencies
are not included in the `[project]` table.

Development dependencies can have entries in `tool.uv.sources` the same as normal dependencies.

To add a development dependency, use the `--dev` flag:

```console
$ uv add --dev pytest
```

uv uses the `[dependency-groups]` table (as defined in [PEP 735](https://peps.python.org/pep-0735/))
for declaration of development dependencies. The above command will create a `dev` group:

```toml title="pyproject.toml"
[dependency-groups]
dev = [
  "pytest >=8.1.1,<9"
]
```

The `dev` group is special-cased; there are `--dev`, `--only-dev`, and `--no-dev` flags to toggle
inclusion or exclusion of its dependencies. See `--no-default-groups` to disable all default groups
instead. Additionally, the `dev` group is [synced by default](#default-groups).
```

**[5] guides/migration/pip-to-project.md**

```text
#### Importing development dependency files

As discussed in the [development dependencies](#development-dependencies) section, it's common to
have groups of dependencies for development purposes.

To import development dependencies, use the `--dev` flag during `uv add`:

```console
$ uv add --dev -r requirements-dev.in -c requirements-dev.txt
```

If the `requirements-dev.in` includes the parent `requirements.in` via `-r`, it will need to be
stripped to avoid adding the base requirements to the `dev` dependency group. The following example
uses `sed` to strip lines that start with `-r`, then pipes the result to `uv add`:

```console
$ sed '/^-r /d' requirements-dev.in | uv add --dev -r - -c requirements-dev.txt
```

In addition to the `dev` dependency group, uv supports arbitrary group names. For example, if you
also have a dedicated set of dependencies for building your documentation, those can be imported to
a `docs` group:

```console
$ uv add -r requirements-docs.in -c requirements-docs.txt --group docs
```

#### Importing dependency sources

When importing requirements on local paths or Git repositories, for example:

```requirements title="requirements.in"
./path-dep
-e ./editable-path-dep
git-dep @ git+https://github.com/astral-sh/git-dep
```

uv will map them to [dependency sources](../../concepts/projects/dependencies.md#dependency-sources)
in the `[tool.uv.sources]` table of the `pyproject.toml`:

```toml title="pyproject.toml"
[project]
dependencies = [
    "path-dep",
    "editable-path-dep",
    "git-dep",
]

[tool.uv.sources]
path-dep = { path = "./path-dep" }
editable-path-dep = { path = "./editable-path-dep", editable = true }
git-dep = { git = "https://github.com/astral-sh/git-dep" }
```
```

</details>

## 15. `f26cd1ce-2eaa-512b-a233-b512b946c021` (summary, ko)

**질문**: uv의 PyTorch 백엔드 선택 기능은 어떻게 동작하며, 어디에서 사용할 수 있나요?

**답**:

```text
uv는 `--torch-backend=auto` 명령줄 인자 또는 `UV_TORCH_BACKEND=auto` 환경 변수로 PyTorch 인덱스를 자동 선택합니다 [2]. 이 기능이 켜지면 uv는 설치된 CUDA 드라이버, AMD GPU 버전, Intel GPU 존재 여부를 확인한 뒤, `torch`, `torchvision` 등 관련 패키지 전체에 가장 호환되는 PyTorch 인덱스를 사용합니다 [2]. 해당 GPU가 없으면 CPU 전용 인덱스로 대체됩니다 [2]. PyTorch 생태계 밖의 패키지에는 기존 인덱스 설정이 그대로 적용됩니다 [2].

특정 백엔드를 직접 지정할 수도 있습니다. 예를 들어 `--torch-backend=cu130` 또는 `UV_TORCH_BACKEND=cu130`으로 CUDA 13.0을 선택할 수 있습니다 [2].

사용 위치는 `uv pip` 인터페이스로 제한됩니다. 현재 `--torch-backend`는 `uv pip` 인터페이스에서만 사용할 수 있습니다 [2]. 프로젝트 인터페이스(`uv lock`, `uv sync`, `uv run`)에서는 `pyproject.toml`의 `[[tool.uv.index]]`와 `[tool.uv.sources]`로 PyTorch 인덱스를 지정하는 방식을 사용합니다 [1][3][4].

참고로 가이드의 일부 기능은 uv 0.5.3 이상이 필요하며, PyTorch 설정 전에 업그레이드하는 것이 권장됩니다 [1].
```

**인용 판정 대상**(문장, 가리키는 근거 번호):

0. [2] uv는 `--torch-backend=auto` 명령줄 인자 또는 `UV_TORCH_BACKEND=auto` 환경 변수로 PyTorch 인덱스를 자동 선택합니다 [2].
1. [2] 이 기능이 켜지면 uv는 설치된 CUDA 드라이버, AMD GPU 버전, Intel GPU 존재 여부를 확인한 뒤, `torch`, `torchvision` 등 관련 패키지 전체에 가장 호환되는 PyTorch 인덱스를 사용합니다 [2].
2. [2] 해당 GPU가 없으면 CPU 전용 인덱스로 대체됩니다 [2].
3. [2] PyTorch 생태계 밖의 패키지에는 기존 인덱스 설정이 그대로 적용됩니다 [2].
4. [2] 예를 들어 `--torch-backend=cu130` 또는 `UV_TORCH_BACKEND=cu130`으로 CUDA 13.0을 선택할 수 있습니다 [2].
5. [2] 현재 `--torch-backend`는 `uv pip` 인터페이스에서만 사용할 수 있습니다 [2].
6. [1] 프로젝트 인터페이스(`uv lock`, `uv sync`, `uv run`)에서는 `pyproject.toml`의 `[[tool.uv.index]]`와 `[tool.uv.sources]`로 PyTorch 인덱스를 지정하는 방식을 사용합니다 [1][3][4].
7. [3] 프로젝트 인터페이스(`uv lock`, `uv sync`, `uv run`)에서는 `pyproject.toml`의 `[[tool.uv.index]]`와 `[tool.uv.sources]`로 PyTorch 인덱스를 지정하는 방식을 사용합니다 [1][3][4].
8. [4] 프로젝트 인터페이스(`uv lock`, `uv sync`, `uv run`)에서는 `pyproject.toml`의 `[[tool.uv.index]]`와 `[tool.uv.sources]`로 PyTorch 인덱스를 지정하는 방식을 사용합니다 [1][3][4].
9. [1] 참고로 가이드의 일부 기능은 uv 0.5.3 이상이 필요하며, PyTorch 설정 전에 업그레이드하는 것이 권장됩니다 [1].

**핵심 요점**:

0. Identifies the command-line flag or environment variable for automatic selection.
1. Explains GPU detection, compatible index selection, and CPU-only fallback.
2. States that existing index configuration is preserved for packages outside the PyTorch ecosystem.
3. Notes that a specific backend can be selected and that backend selection is currently limited to `uv pip`.

**금지 내용**:

0. Claims automatic selection always uses a GPU index even when no supported GPU is found.
1. Claims `--torch-backend` is currently available in uv's project interface.

<details><summary>근거 문서</summary>

**[1] guides/integration/pytorch.md**

```text
# Using uv with PyTorch

The [PyTorch](https://pytorch.org/) ecosystem is a popular choice for deep learning research and
development. You can use uv to manage PyTorch projects and PyTorch dependencies across different
Python versions and environments, even controlling for the choice of accelerator (e.g., CPU-only vs.
CUDA).

!!! note

    Some of the features outlined in this guide require uv version 0.5.3 or later. We recommend upgrading prior to configuring PyTorch.
```

**[2] guides/integration/pytorch.md**

```text
## The `uv pip` interface

While the above examples are focused on uv's project interface (`uv lock`, `uv sync`, `uv run`,
etc.), PyTorch can also be installed via the `uv pip` interface.

PyTorch itself offers a [dedicated interface](https://pytorch.org/get-started/locally/) to determine
the appropriate pip command to run for a given target configuration. For example, you can install
stable, CPU-only PyTorch on Linux with:

```shell
$ pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

To use the same workflow with uv, replace `pip3` with `uv pip`:

```shell
$ uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

## Automatic backend selection

uv supports automatic selection of the appropriate PyTorch index via the `--torch-backend=auto`
command-line argument (or the `UV_TORCH_BACKEND=auto` environment variable), as in:

```shell
$ # With a command-line argument.
$ uv pip install torch --torch-backend=auto

$ # With an environment variable.
$ UV_TORCH_BACKEND=auto uv pip install torch
```

When enabled, uv will query for the installed CUDA driver, AMD GPU versions, and Intel GPU presence,
then use the most-compatible PyTorch index for all relevant packages (e.g., `torch`, `torchvision`,
etc.). If no such GPU is found, uv will fall back to the CPU-only index. uv will continue to respect
existing index configuration for any packages outside the PyTorch ecosystem.

You can also select a specific backend (e.g., CUDA 13.0) with `--torch-backend=cu130` (or
`UV_TORCH_BACKEND=cu130`):

```shell
$ # With a command-line argument.
$ uv pip install torch torchvision --torch-backend=cu130

$ # With an environment variable.
$ UV_TORCH_BACKEND=cu130 uv pip install torch torchvision
```

At present, `--torch-backend` is only available in the `uv pip` interface.
```

**[3] guides/integration/pytorch.md**

```text
=== "Intel GPUs"

    ```toml
    [[tool.uv.index]]
    name = "pytorch-xpu"
    url = "https://download.pytorch.org/whl/xpu"
    explicit = true
    ```

We recommend the use of `explicit = true` to ensure that the index is _only_ used for `torch`,
`torchvision`, and other PyTorch-related packages, as opposed to generic dependencies like `jinja2`,
which should continue to be sourced from the default index (PyPI).

Next, update the `pyproject.toml` to point `torch` and `torchvision` to the desired index:

=== "CPU-only"

    ```toml
    [tool.uv.sources]
    torch = [
      { index = "pytorch-cpu" },
    ]
    torchvision = [
      { index = "pytorch-cpu" },
    ]
    ```

=== "CUDA 11.8"

    PyTorch doesn't publish CUDA builds for macOS. As such, we gate on `sys_platform` to instruct uv to use
    the PyTorch index on Linux and Windows, but fall back to PyPI on macOS:

    ```toml
    [tool.uv.sources]
    torch = [
      { index = "pytorch-cu118", marker = "sys_platform == 'linux' or sys_platform == 'win32'" },
    ]
    torchvision = [
      { index = "pytorch-cu118", marker = "sys_platform == 'linux' or sys_platform == 'win32'" },
    ]
    ```

=== "CUDA 12.6"

    PyTorch doesn't publish CUDA builds for macOS. As such, we gate on `sys_platform` to instruct uv to limit
    the PyTorch index to Linux and Windows, falling back to PyPI on macOS:

    ```toml
    [tool.uv.sources]
    torch = [
      { index = "pytorch-cu126", marker = "sys_platform == 'linux' or sys_platform == 'win32'" },
    ]
    torchvision = [
      { index = "pytorch-cu126", marker = "sys_platform == 'linux' or sys_platform == 'win32'" },
    ]
    ```

=== "CUDA 12.8"
```

**[4] guides/integration/pytorch.md**

```text
=== "CUDA 12.8"

    PyTorch doesn't publish CUDA builds for macOS. As such, we gate on `sys_platform` to instruct uv to limit
    the PyTorch index to Linux and Windows, falling back to PyPI on macOS:

    ```toml
    [tool.uv.sources]
    torch = [
      { index = "pytorch-cu128", marker = "sys_platform == 'linux' or sys_platform == 'win32'" },
    ]
    torchvision = [
      { index = "pytorch-cu128", marker = "sys_platform == 'linux' or sys_platform == 'win32'" },
    ]
    ```

=== "CUDA 13.0"

    PyTorch doesn't publish CUDA builds for macOS. As such, we gate on `sys_platform` to instruct uv to limit
    the PyTorch index to Linux and Windows, falling back to PyPI on macOS:

    ```toml
    [tool.uv.sources]
    torch = [
      { index = "pytorch-cu130", marker = "sys_platform == 'linux' or sys_platform == 'win32'" },
    ]
    torchvision = [
      { index = "pytorch-cu130", marker = "sys_platform == 'linux' or sys_platform == 'win32'" },
    ]
    ```

=== "ROCm 7.2"

    PyTorch doesn't publish ROCm builds for macOS or Windows. As such, we gate on `sys_platform` to instruct uv
    to limit the PyTorch index to Linux, falling back to PyPI on macOS and Windows:
```

**[5] concepts/projects/dependencies.md**

```text
[project.optional-dependencies]
cpu = [
  "torch",
]
gpu = [
  "torch",
]

[tool.uv.sources]
torch = [
  { index = "torch-cpu", extra = "cpu" },
  { index = "torch-gpu", extra = "gpu" },
]

[[tool.uv.index]]
name = "torch-cpu"
url = "https://download.pytorch.org/whl/cpu"

[[tool.uv.index]]
name = "torch-gpu"
url = "https://download.pytorch.org/whl/cu130"
```
```

</details>

## 16. `2b0ee2c5-2cc0-5208-9aa1-4651f57185c9` (trap, en)

**질문**: In the official uv pre-commit integration, how should I configure a hook to compile requirements-dev.in into requirements-dev.txt and match changes to either file?

**답**:

```text
Add a `pip-compile` hook under the uv-pre-commit repo in `.pre-commit-config.yaml`, with `args` set to compile `requirements-dev.in` into `requirements-dev.txt` and a `files` regex that matches both files [1]:

```yaml title=".pre-commit-config.yaml"
repos:
  - repo: https://github.com/astral-sh/uv-pre-commit
    # uv version.
    rev: 0.13.7
    hooks:
      # Compile requirements
      - id: pip-compile
        args: [requirements-dev.in, -o, requirements-dev.txt]
        files: ^requirements-dev\.(in|txt)$
```

The `files` pattern `^requirements-dev\.(in|txt)$` makes the hook run when either `requirements-dev.in` or `requirements-dev.txt` changes [1]. The docs describe this pattern as the way to compile alternative requirements files by modifying `args` and `files` [1].
```

**인용 판정 대상**(문장, 가리키는 근거 번호):

0. [1] Add a `pip-compile` hook under the uv-pre-commit repo in `.pre-commit-config.yaml`, with `args` set to compile `requirements-dev.in` into `requirements-dev.txt` and a `files` regex that matches both files [1]:
1. [1] The `files` pattern `^requirements-dev\.(in|txt)$` makes the hook run when either `requirements-dev.in` or `requirements-dev.txt` changes [1].
2. [1] The docs describe this pattern as the way to compile alternative requirements files by modifying `args` and `files` [1].

**핵심 요점**:

0. Uses the hook ID `pip-compile`.
1. Specifies arguments `requirements-dev.in`, `-o`, and `requirements-dev.txt` in that order.
2. Uses `files: ^requirements-dev\.(in|txt)$` or an equivalent pattern matching both files.

**금지 내용**:

0. Uses `uv-pip-compile` as the hook ID.

<details><summary>근거 문서</summary>

**[1] guides/integration/pre-commit.md**

```text
# Using uv in pre-commit

An official pre-commit hook is provided at
[`astral-sh/uv-pre-commit`](https://github.com/astral-sh/uv-pre-commit).

To use uv with pre-commit, add one of the following examples to the `repos` list in the
`.pre-commit-config.yaml`.

To make sure your `uv.lock` file is up to date even if your `pyproject.toml` file was changed:

```yaml title=".pre-commit-config.yaml"
repos:
  - repo: https://github.com/astral-sh/uv-pre-commit
    # uv version.
    rev: 0.13.7
    hooks:
      - id: uv-lock
```

To keep a `requirements.txt` file in sync with your `uv.lock` file:

```yaml title=".pre-commit-config.yaml"
repos:
  - repo: https://github.com/astral-sh/uv-pre-commit
    # uv version.
    rev: 0.13.7
    hooks:
      - id: uv-export
```

To compile requirements files:

```yaml title=".pre-commit-config.yaml"
repos:
  - repo: https://github.com/astral-sh/uv-pre-commit
    # uv version.
    rev: 0.13.7
    hooks:
      # Compile requirements
      - id: pip-compile
        args: [requirements.in, -o, requirements.txt]
```

To compile alternative requirements files, modify `args` and `files`:

```yaml title=".pre-commit-config.yaml"
repos:
  - repo: https://github.com/astral-sh/uv-pre-commit
    # uv version.
    rev: 0.13.7
    hooks:
      # Compile requirements
      - id: pip-compile
        args: [requirements-dev.in, -o, requirements-dev.txt]
        files: ^requirements-dev\.(in|txt)$
```

To run the hook over multiple files at the same time, add additional entries:
```

**[2] guides/integration/pre-commit.md**

```text
To run the hook over multiple files at the same time, add additional entries:

```yaml title=".pre-commit-config.yaml"
repos:
  - repo: https://github.com/astral-sh/uv-pre-commit
    # uv version.
    rev: 0.13.7
    hooks:
      # Compile requirements
      - id: pip-compile
        name: pip-compile requirements.in
        args: [requirements.in, -o, requirements.txt]
      - id: pip-compile
        name: pip-compile requirements-dev.in
        args: [requirements-dev.in, -o, requirements-dev.txt]
        files: ^requirements-dev\.(in|txt)$
```
```

**[3] pip/compile.md**

```text
## Locking requirements

uv allows dependencies to be locked in the `requirements.txt` format. It is recommended to use the
standard `pyproject.toml` to define dependencies, but other dependency formats are supported as
well. See the documentation on [declaring dependencies](dependencies.md) for more details on how to
define dependencies.

To lock dependencies declared in a `pyproject.toml`:

```console
$ uv pip compile pyproject.toml -o requirements.txt
```

By default, `uv pip compile` displays its output. Use the `--output-file` / `-o` argument to write
it to a file.

To lock dependencies declared in a `requirements.in`:

```console
$ uv pip compile requirements.in -o requirements.txt
```

To lock dependencies declared in multiple files:

```console
$ uv pip compile pyproject.toml requirements-dev.in -o requirements-dev.txt
```

uv also supports legacy `setup.py` and `setup.cfg` formats. To lock dependencies declared in a
`setup.py`:

```console
$ uv pip compile setup.py -o requirements.txt
```

To lock dependencies from stdin, use `-`:

```console
$ echo "ruff" | uv pip compile -
```

To lock with optional dependencies enabled, e.g., the "foo" extra:

```console
$ uv pip compile pyproject.toml --extra foo
```

To lock with all optional dependencies enabled:

```console
$ uv pip compile pyproject.toml --all-extras
```

Note extras are not supported with the `requirements.in` format.

To lock a dependency group in the current project directory's `pyproject.toml`, for example the
group `foo`:

```console
$ uv pip compile --group foo
```

!!! important

    A `--group` flag has to be added to pip-tools' `pip compile`, [although they're considering it](https://github.com/jazzband/pip-tools/issues/2062). We expect to support whatever syntax and semantics they adopt.

To specify the project directory where groups should be sourced from:

```console
$ uv pip compile --project some/path/ --group foo --group bar
```

Alternatively, you can specify a path to a `pyproject.toml` for each group:

```console
$ uv pip compile --group some/path/pyproject.toml:foo --group other/pyproject.toml:bar
```

!!! note
```

**[4] guides/migration/pip-to-project.md**

```text
#### Importing development dependency files

As discussed in the [development dependencies](#development-dependencies) section, it's common to
have groups of dependencies for development purposes.

To import development dependencies, use the `--dev` flag during `uv add`:

```console
$ uv add --dev -r requirements-dev.in -c requirements-dev.txt
```

If the `requirements-dev.in` includes the parent `requirements.in` via `-r`, it will need to be
stripped to avoid adding the base requirements to the `dev` dependency group. The following example
uses `sed` to strip lines that start with `-r`, then pipes the result to `uv add`:

```console
$ sed '/^-r /d' requirements-dev.in | uv add --dev -r - -c requirements-dev.txt
```

In addition to the `dev` dependency group, uv supports arbitrary group names. For example, if you
also have a dedicated set of dependencies for building your documentation, those can be imported to
a `docs` group:

```console
$ uv add -r requirements-docs.in -c requirements-docs.txt --group docs
```

#### Importing dependency sources

When importing requirements on local paths or Git repositories, for example:

```requirements title="requirements.in"
./path-dep
-e ./editable-path-dep
git-dep @ git+https://github.com/astral-sh/git-dep
```

uv will map them to [dependency sources](../../concepts/projects/dependencies.md#dependency-sources)
in the `[tool.uv.sources]` table of the `pyproject.toml`:

```toml title="pyproject.toml"
[project]
dependencies = [
    "path-dep",
    "editable-path-dep",
    "git-dep",
]

[tool.uv.sources]
path-dep = { path = "./path-dep" }
editable-path-dep = { path = "./editable-path-dep", editable = true }
git-dep = { git = "https://github.com/astral-sh/git-dep" }
```
```

**[5] pip/compile.md**

```text
## Upgrading requirements

When using an output file, uv will consider the versions pinned in an existing output file. If a
dependency is pinned it will not be upgraded on a subsequent compile run. For example:

```console
$ echo "ruff==0.3.0" > requirements.txt
$ echo "ruff" | uv pip compile - -o requirements.txt
# This file was autogenerated by uv via the following command:
#    uv pip compile - -o requirements.txt
ruff==0.3.0
```

To upgrade a dependency, use the `--upgrade-package` flag:

```console
$ uv pip compile - -o requirements.txt --upgrade-package ruff
```

To upgrade all dependencies, there is an `--upgrade` flag.

## Syncing an environment

Dependencies can be installed directly from their definition files or from compiled
`requirements.txt` files with `uv pip install`. See the documentation on
[installing packages from files](packages.md#installing-packages-from-files) for more details.

When installing with `uv pip install`, packages that are already installed will not be removed
unless they conflict with the lockfile. This means that the environment can have dependencies that
aren't declared in the lockfile, which isn't great for reproducibility. To ensure the environment
exactly matches the lockfile, use `uv pip sync` instead.

To sync an environment with a `requirements.txt` file:

```console
$ uv pip sync requirements.txt
```

To sync an environment with a [PEP 751](https://peps.python.org/pep-0751/) `pylock.toml` file:

```console
$ uv pip sync pylock.toml
```
```

</details>

## 17. `aa8544de-8a06-54b5-a387-83ad37285cdc` (trap, en)

**질문**: On Windows, if I invoke a legacy tool script with uvx without specifying its file extension, which extensions are checked, and in what order?

**답**:

```text
When you invoke a legacy script with `uvx` on Windows without specifying its extension, uv looks for files ending in `.ps1`, `.cmd`, and `.bat`, in that order of execution [3]. Only legacy scripts with these three extensions are supported [3].
```

**인용 판정 대상**(문장, 가리키는 근거 번호):

0. [3] When you invoke a legacy script with `uvx` on Windows without specifying its extension, uv looks for files ending in `.ps1`, `.cmd`, and `.bat`, in that order of execution [3].
1. [3] Only legacy scripts with these three extensions are supported [3].

**핵심 요점**:

0. Says `.ps1` is checked first.
1. Says `.cmd` is checked second.
2. Says `.bat` is checked third.

**금지 내용**:

0. Claims that the extension must be specified.
1. Gives a different search order.

<details><summary>근거 문서</summary>

**[1] concepts/projects/run.md**

```text
## Legacy scripts on Windows

Support is provided for
[legacy setuptools scripts](https://packaging.python.org/en/latest/guides/distributing-packages-using-setuptools/#scripts).
These types of scripts are additional files installed by setuptools in `.venv\Scripts`.

Currently only legacy scripts with the `.ps1`, `.cmd`, and `.bat` extensions are supported.

For example, to run a Command Prompt script:

```console
$ uv run --with nuitka==2.6.7 -- nuitka.cmd --version
```

In addition, you don't need to specify the extension. `uv` will automatically look for files ending
in `.ps1`, `.cmd`, and `.bat` in that order of execution on your behalf.

```console
$ uv run --with nuitka==2.6.7 -- nuitka --version
```

## Signal handling

uv does not cede control of the process to the spawned command in order to provide better error
messages on failure. Consequently, uv is responsible for forwarding some signals to the child
process the requested command runs in.

On Unix systems, uv will forward most signals (with the exception of SIGKILL, SIGCHLD, SIGIO, and
SIGPOLL) to the child process. Since terminals send SIGINT to the foreground process group on
Ctrl-C, uv will only forward a SIGINT to the child process if it is sent more than once or the child
process group differs from uv's.

On Windows, these concepts do not apply and uv ignores Ctrl-C events, deferring handling to the
child process so it can exit cleanly.
```

**[2] guides/tools.md**

```text
# Using tools

Many Python packages provide applications that can be used as tools. uv has specialized support for
easily invoking and installing tools.

## Running tools

The `uvx` command invokes a tool without installing it.

For example, to run `ruff`:

```console
$ uvx ruff
```

!!! note

    This is exactly equivalent to:

    ```console
    $ uv tool run ruff
    ```

    `uvx` is provided as an alias for convenience.

Arguments can be provided after the tool name:

```console
$ uvx pycowsay hello from uv

  -------------
< hello from uv >
  -------------
   \   ^__^
    \  (oo)\_______
       (__)\       )\/\
           ||----w |
           ||     ||

```

Tools are installed into temporary, isolated environments when using `uvx`.

!!! note

    If you are running a tool in a [_project_](../concepts/projects/index.md) and the tool requires that
    your project is installed, e.g., when using `pytest` or `mypy`, you'll want to use
    [`uv run`](./projects.md#running-commands) instead of `uvx`. Otherwise, the tool will be run in
    a virtual environment that is isolated from your project.

    If your project has a flat structure, e.g., instead of using a `src` directory for modules,
    the project itself does not need to be installed and `uvx` is fine. In this case, using
    `uv run` is only beneficial if you want to pin the version of the tool in the project's
    dependencies.

## Commands with different package names

When `uvx ruff` is invoked, uv installs the `ruff` package which provides the `ruff` command.
However, sometimes the package and command names differ.

The `--from` option can be used to invoke a command from a specific package, e.g., `http` which is
provided by `httpie`:

```console
$ uvx --from httpie http
```
```

**[3] guides/tools.md**

```text
## Upgrading tools

To upgrade a tool, use `uv tool upgrade`:

```console
$ uv tool upgrade ruff
```

Tool upgrades will respect the version constraints provided when installing the tool. For example,
`uv tool install ruff >=0.3,<0.4` followed by `uv tool upgrade ruff` will upgrade Ruff to the latest
version in the range `>=0.3,<0.4`.

To instead replace the version constraints, re-install the tool with `uv tool install`:

```console
$ uv tool install ruff>=0.4
```

To instead upgrade all tools:

```console
$ uv tool upgrade --all
```

## Requesting Python versions

By default, uv will use your default Python interpreter (the first it finds) when running,
installing, or upgrading tools. You can specify the Python interpreter to use with the `--python`
option.

For example, to request a specific Python version when running a tool:

```console
$ uvx --python 3.10 ruff
```

Or, when installing a tool:

```console
$ uv tool install --python 3.10 ruff
```

Or, when upgrading a tool:

```console
$ uv tool upgrade --python 3.10 ruff
```

For more details on requesting Python versions, see the
[Python version](../concepts/python-versions.md#requesting-a-version) concept page.

## Legacy Windows Scripts

Tools also support running
[legacy setuptools scripts](https://packaging.python.org/en/latest/guides/distributing-packages-using-setuptools/#scripts).
These scripts are available via `$(uv tool dir)\<tool-name>\Scripts` when installed.

Currently only legacy scripts with the `.ps1`, `.cmd`, and `.bat` extensions are supported.

For example, to run a Command Prompt script:

```console
$ uv tool run --from nuitka==2.6.7 nuitka.cmd --version
```

In addition, you don't need to specify the extension. `uvx` will automatically look for files ending
in `.ps1`, `.cmd`, and `.bat` in that order of execution on your behalf.

```console
$ uv tool run --from nuitka==2.6.7 nuitka --version
```
```

**[4] concepts/tools.md**

```text
## Tool executables

Tool executables include all console entry points, script entry points, and binary scripts provided
by a Python package. Tool executables are symlinked into the
[executable directory](../reference/storage.md#tool-executables) on Unix and copied on Windows.

!!! note

    Executables provided by dependencies of tool packages are not installed.

The [executable directory](../reference/storage.md#executable-directory) must be in the `PATH`
variable for tool executables to be available from the shell. If it is not in the `PATH`, a warning
will be displayed. The `uv tool update-shell` command can be used to add the executable directory to
the `PATH` in common shell configuration files.

### Overwriting executables

Installation of tools will not overwrite executables in the executable directory that were not
previously installed by uv. For example, if `pipx` has been used to install a tool,
`uv tool install` will fail. The `--force` flag can be used to override this behavior.

## Relationship to `uv run`

The invocation `uv tool run <name>` (or `uvx <name>`) is nearly equivalent to:

```console
$ uv run --no-project --with <name> -- <name>
```

However, there are a couple notable differences when using uv's tool interface:

- The `--with` option is not needed — the required package is inferred from the command name.
- The temporary environment is cached in a dedicated location.
- The `--no-project` flag is not needed — tools are always run isolated from the project.
- If a tool is already installed, `uv tool run` will use the installed version but `uv run` will
  not.

If the tool should not be isolated from the project, e.g., when running `pytest` or `mypy`, then
`uv run` should be used instead of `uv tool run`.
```

**[5] index.md**

```text
## Tools

uv executes and installs command-line tools provided by Python packages, similar to `pipx`.

Run a tool in an ephemeral environment using `uvx` (an alias for `uv tool run`):

```console
$ uvx pycowsay 'hello world!'
Resolved 1 package in 167ms
Installed 1 package in 9ms
 + pycowsay==0.0.0.2
  """

  ------------
< hello world! >
  ------------
   \   ^__^
    \  (oo)\_______
       (__)\       )\/\
           ||----w |
           ||     ||
```

Install a tool with `uv tool install`:

```console
$ uv tool install ruff
Resolved 1 package in 6ms
Installed 1 package in 2ms
 + ruff==0.5.4
Installed 1 executable: ruff

$ ruff --version
ruff 0.5.4
```

See the [tools guide](./guides/tools.md) to get started.
```

</details>

## 18. `e94e4c68-4397-5c01-9604-6bc5e9c6ad38` (trap, en)

**질문**: In a uv workspace, the root configures a Git source for a dependency, but one member configures its own source for that dependency with a Windows-only marker. When resolving that member on Linux, does uv fall back to the root's Git source?

**답**:

```text
No. uv does not fall back to the root's Git source on Linux. A member's own `tool.uv.sources` entry overrides the root's entry for the same dependency, even when the member's entry is limited by a marker that doesn't match the current platform [4]. On Linux, the Windows-only marker doesn't match, so the root's Git source is ignored.

The documents describe the non-matching case only for a single source with a marker. There, uv includes the dependency on all platforms and falls back to PyPI on platforms where the marker doesn't match [5]. The documents don't explicitly state where the dependency is resolved in this workspace case, so I can't confirm that it resolves from PyPI.
```

**인용 판정 대상**(문장, 가리키는 근거 번호):

0. [4] A member's own `tool.uv.sources` entry overrides the root's entry for the same dependency, even when the member's entry is limited by a marker that doesn't match the current platform [4].
1. [5] There, uv includes the dependency on all platforms and falls back to PyPI on platforms where the marker doesn't match [5].

**핵심 요점**:

0. States that uv does not fall back to the root's Git source.
1. Explains that the member's source entry overrides the root entry even when its marker does not match.

**금지 내용**:

0. Claims that a nonmatching member marker causes uv to use the workspace root's source.

<details><summary>근거 문서</summary>

**[1] concepts/projects/workspaces.md**

```text
## Workspace sources

Within a workspace, dependencies on workspace members are facilitated via
[`tool.uv.sources`](./dependencies.md), as in:

```toml title="pyproject.toml"
[project]
name = "albatross"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["bird-feeder", "tqdm>=4,<5"]

[tool.uv.sources]
bird-feeder = { workspace = true }

[tool.uv.workspace]
members = ["packages/*"]

[build-system]
requires = ["uv_build>=0.13.7,<0.14"]
build-backend = "uv_build"
```

In this example, the `albatross` project depends on the `bird-feeder` project, which is a member of
the workspace. The `workspace = true` key-value pair in the `tool.uv.sources` table indicates the
`bird-feeder` dependency should be provided by the workspace, rather than fetched from PyPI or
another registry. The `workspace` field can also be set to a path string to resolve a dependency
from a different workspace. The path is resolved relative to the project that declares the source
(or the workspace root for a workspace-level source) and must point to the external workspace root.
uv selects the member that matches the dependency name.

!!! note

    Dependencies between workspace members are editable.

Any `tool.uv.sources` definitions in the workspace root apply to all members, unless overridden in
the `tool.uv.sources` of a specific member. For example, given the following `pyproject.toml`:

```toml title="pyproject.toml"
[project]
name = "albatross"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["bird-feeder", "tqdm>=4,<5"]

[tool.uv.sources]
bird-feeder = { workspace = true }
tqdm = { git = "https://github.com/tqdm/tqdm" }

[tool.uv.workspace]
members = ["packages/*"]

[build-system]
requires = ["uv_build>=0.13.7,<0.14"]
build-backend = "uv_build"
```
```

**[2] concepts/projects/dependencies.md**

```text
## Dependency sources

The `tool.uv.sources` table extends the standard dependency tables with alternative dependency
sources, which are used during development.

Dependency sources add support for common patterns that are not supported by the
`project.dependencies` standard, like editable installations and relative paths. For example, to
install `foo` from a directory relative to the project root:

```toml title="pyproject.toml" hl_lines="7"
[project]
name = "example"
version = "0.1.0"
dependencies = ["foo"]

[tool.uv.sources]
foo = { path = "./packages/foo" }
```

The following dependency sources are supported by uv:

- [Index](#index): A package resolved from a specific package index.
- [Git](#git): A Git repository.
- [URL](#url): A remote wheel or source distribution.
- [Path](#path): A local wheel, source distribution, or project directory.
- [Workspace](#workspace-member): A member of the current workspace.

!!! important

    Sources are only respected by uv. If another tool is used, only the definitions in the standard
    project tables will be used. If another tool is being used for development, any metadata
    provided in the source table will need to be re-specified in the other tool's format.
```

**[3] concepts/projects/dependencies.md**

```text
### Git

To add a Git dependency source, prefix a Git-compatible URL with `git+`.

For example:

```console
$ # Install over HTTP(S).
$ uv add git+https://github.com/encode/httpx

$ # Install over SSH.
$ uv add git+ssh://git@github.com/encode/httpx
```

```toml title="pyproject.toml" hl_lines="5"
[project]
dependencies = ["httpx"]

[tool.uv.sources]
httpx = { git = "https://github.com/encode/httpx" }
```

Specific Git references can be requested, e.g., a tag:

```console
$ uv add git+https://github.com/encode/httpx --tag 0.27.0
```

```toml title="pyproject.toml" hl_lines="7"
[project]
dependencies = ["httpx"]

[tool.uv.sources]
httpx = { git = "https://github.com/encode/httpx", tag = "0.27.0" }
```

Or, a branch:

```console
$ uv add git+https://github.com/encode/httpx --branch main
```

```toml title="pyproject.toml" hl_lines="7"
[project]
dependencies = ["httpx"]

[tool.uv.sources]
httpx = { git = "https://github.com/encode/httpx", branch = "main" }
```

Or, a revision (commit):

```console
$ uv add git+https://github.com/encode/httpx --rev 326b9431c761e1ef1e00b9f760d1f654c8db48c6
```

```toml title="pyproject.toml" hl_lines="7"
[project]
dependencies = ["httpx"]

[tool.uv.sources]
httpx = { git = "https://github.com/encode/httpx", rev = "326b9431c761e1ef1e00b9f760d1f654c8db48c6" }
```

A `subdirectory` may be specified if the package isn't in the repository root:

```console
$ uv add git+https://github.com/langchain-ai/langchain#subdirectory=libs/langchain
```
```

**[4] concepts/projects/workspaces.md**

```text
[tool.uv.workspace]
members = ["packages/*"]

[build-system]
requires = ["uv_build>=0.13.7,<0.14"]
build-backend = "uv_build"
```

Every workspace member would, by default, install `tqdm` from GitHub, unless a specific member
overrides the `tqdm` entry in its own `tool.uv.sources` table.

!!! note

    If a workspace member provides `tool.uv.sources` for some dependency, it will ignore any
    `tool.uv.sources` for the same dependency in the workspace root, even if the member's source is
    limited by a [marker](dependencies.md#platform-specific-sources) that doesn't match the current
    platform.
```

**[5] concepts/projects/dependencies.md**

```text
### Workspace member

To declare a dependency on a workspace member, add the member name with `{ workspace = true }`. All
workspace members must be explicitly stated. Workspace members are always
[editable](#editable-dependencies). See the [workspace](./workspaces.md) documentation for more
details on workspaces.

To source a dependency from a different workspace, `workspace` can also be a path string:

```toml title="pyproject.toml"
[tool.uv.sources]
foo = { workspace = "../other-workspace" }
```

```toml title="pyproject.toml"
[project]
dependencies = ["foo==0.1.0"]

[tool.uv.sources]
foo = { workspace = true }

[tool.uv.workspace]
members = [
  "packages/foo"
]
```

### Platform-specific sources

You can limit a source to a given platform or Python version by providing
[dependency specifiers](https://packaging.python.org/en/latest/specifications/dependency-specifiers/)-compatible
environment markers for the source.

For example, to pull `httpx` from GitHub, but only on macOS, use the following:

```toml title="pyproject.toml" hl_lines="8"
[project]
dependencies = ["httpx"]

[tool.uv.sources]
httpx = { git = "https://github.com/encode/httpx", tag = "0.27.2", marker = "sys_platform == 'darwin'" }
```

By specifying the marker on the source, uv will still include `httpx` on all platforms, but will
download the source from GitHub on macOS, and fall back to PyPI on all other platforms.
```

</details>

## 19. `ed74fbbc-b4f1-5f45-9e64-18f7f51a914c` (trap, en)

**질문**: My pyproject.toml still lists test tools under `[tool.uv] dev-dependencies`. If I run `uv add --dev pytest`, where does uv record pytest, and is that field still the recommended place for development dependencies?

**답**:

```text
`uv add --dev pytest` records pytest in the `[dependency-groups]` table, not in `[tool.uv]`. It creates a `dev` group, so the entry looks like this:

```toml
[dependency-groups]
dev = [
  "pytest >=8.1.1,<9"
]
```

[1] uv uses the `[dependency-groups]` table, as defined in PEP 735, for declaring development dependencies [1]. The documents also say development dependencies are not included in the `[project]` table [1].

The documents don't mention `[tool.uv] dev-dependencies` at all, so they don't say whether that field is deprecated or still recommended. What they do say is that `[dependency-groups]` is the table uv uses for development dependencies [1]. They also note that `dependency-groups` are a recently standardized feature that may not be supported by all tools yet [4].
```

**인용 판정 대상**(문장, 가리키는 근거 번호):

0. [1] [1] uv uses the `[dependency-groups]` table, as defined in PEP 735, for declaring development dependencies [1].
1. [1] The documents also say development dependencies are not included in the `[project]` table [1].
2. [1] What they do say is that `[dependency-groups]` is the table uv uses for development dependencies [1].
3. [4] They also note that `dependency-groups` are a recently standardized feature that may not be supported by all tools yet [4].

**핵심 요점**:

0. States that `uv add --dev` writes to the existing `tool.uv.dev-dependencies` section.
1. States that uv does not create a new `dependency-groups.dev` section in this case.
2. States that `tool.uv.dev-dependencies` is a legacy field that will eventually be deprecated and removed.
3. Identifies the `dev` group in `[dependency-groups]` as the recommended place.

**금지 내용**:

0. Claims `uv add --dev` always writes to `[dependency-groups]`.
1. Claims `tool.uv.dev-dependencies` is already removed or ignored.
2. Presents `tool.uv.dev-dependencies` as the currently recommended field.

<details><summary>근거 문서</summary>

**[1] concepts/projects/dependencies.md**

```text
## Development dependencies

Unlike optional dependencies, development dependencies are local-only and will _not_ be included in
the project requirements when published to PyPI or other indexes. As such, development dependencies
are not included in the `[project]` table.

Development dependencies can have entries in `tool.uv.sources` the same as normal dependencies.

To add a development dependency, use the `--dev` flag:

```console
$ uv add --dev pytest
```

uv uses the `[dependency-groups]` table (as defined in [PEP 735](https://peps.python.org/pep-0735/))
for declaration of development dependencies. The above command will create a `dev` group:

```toml title="pyproject.toml"
[dependency-groups]
dev = [
  "pytest >=8.1.1,<9"
]
```

The `dev` group is special-cased; there are `--dev`, `--only-dev`, and `--no-dev` flags to toggle
inclusion or exclusion of its dependencies. See `--no-default-groups` to disable all default groups
instead. Additionally, the `dev` group is [synced by default](#default-groups).
```

**[2] guides/projects.md**

```text
### `pyproject.toml`

The `pyproject.toml` contains metadata about your project:

```toml title="pyproject.toml"
[project]
name = "hello-world"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
authors = [
  { name = "ferris", email = "ferris@example.org" }
]
requires-python = ">=3.14"
dependencies = []

[project.scripts]
hello-world = "hello_world:main"

[build-system]
requires = ["uv_build>=0.13.7,<0.14"]
build-backend = "uv_build"
```

You'll use this file to specify dependencies, as well as details about the project such as its
description or license. You can edit this file manually, or use commands like `uv add` and
`uv remove` to manage your project from the terminal.

!!! tip

    See the official [`pyproject.toml` guide](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)
    for more details on getting started with the `pyproject.toml` format.

You'll also use this file to specify uv [configuration options](../concepts/configuration-files.md)
in a [`[tool.uv]`](../reference/settings.md) section.

### `.python-version`

The `.python-version` file contains the project's default Python version. This file tells uv which
Python version to use when creating the project's virtual environment.

### `.venv`

The `.venv` folder contains your project's virtual environment, a Python environment that is
isolated from the rest of your system. This is where uv will install your project's dependencies.

See the [project environment](../concepts/projects/layout.md#the-project-environment) documentation
for more details.
```

**[3] getting-started/features.md**

```text
# Features

uv provides essential features for Python development — from installing Python and hacking on simple
scripts to working on large projects that support multiple Python versions and platforms.

uv's interface can be broken down into sections, which are usable independently or together.

## Python versions

Installing and managing Python itself.

- `uv python install`: Install Python versions.
- `uv python list`: View available Python versions.
- `uv python find`: Find an installed Python version.
- `uv python pin`: Pin the current project to use a specific Python version.
- `uv python uninstall`: Uninstall a Python version.

See the [guide on installing Python](../guides/install-python.md) to get started.

## Scripts

Executing standalone Python scripts, e.g., `example.py`.

- `uv run`: Run a script.
- `uv add --script`: Add a dependency to a script.
- `uv remove --script`: Remove a dependency from a script.

See the [guide on running scripts](../guides/scripts.md) to get started.

## Projects

Creating and working on Python projects, i.e., with a `pyproject.toml`.

- `uv init`: Create a new Python project.
- `uv add`: Add a dependency to the project.
- `uv remove`: Remove a dependency from the project.
- `uv sync`: Sync the project's dependencies with the environment.
- `uv lock`: Create a lockfile for the project's dependencies.
- `uv run`: Run a command in the project environment.
- `uv tree`: View the dependency tree for the project.
- `uv build`: Build the project into distribution archives.
- `uv publish`: Publish the project to a package index.

See the [guide on projects](../guides/projects.md) to get started.

## Tools

Running and installing tools published to Python package indexes, e.g., `ruff` or `black`.

- `uvx` / `uv tool run`: Run a tool in a temporary environment.
- `uv tool install`: Install a tool user-wide.
- `uv tool uninstall`: Uninstall a tool.
- `uv tool list`: List installed tools.
- `uv tool update-shell`: Update the shell to include tool executables.

See the [guide on tools](../guides/tools.md) to get started.
```

**[4] concepts/projects/dependencies.md**

```text
# Managing dependencies

## Dependency fields

Dependencies of the project are defined in several fields:

- [`project.dependencies`](#project-dependencies): Published dependencies.
- [`project.optional-dependencies`](#optional-dependencies): Published optional dependencies, or
  "extras".
- [`dependency-groups`](#dependency-groups): Local dependencies for development.
- [`tool.uv.sources`](#dependency-sources): Alternative sources for dependencies during development.

!!! note

    The `project.dependencies` and `project.optional-dependencies` fields can be used even if
    the project isn't going to be published. `dependency-groups` are a recently standardized feature
    and may not be supported by all tools yet.

uv supports modifying the project's dependencies with `uv add` and `uv remove`, but dependency
metadata can also be updated by editing the `pyproject.toml` directly.
```

**[5] guides/migration/pip-to-project.md**

```text
#### Importing development dependency files

As discussed in the [development dependencies](#development-dependencies) section, it's common to
have groups of dependencies for development purposes.

To import development dependencies, use the `--dev` flag during `uv add`:

```console
$ uv add --dev -r requirements-dev.in -c requirements-dev.txt
```

If the `requirements-dev.in` includes the parent `requirements.in` via `-r`, it will need to be
stripped to avoid adding the base requirements to the `dev` dependency group. The following example
uses `sed` to strip lines that start with `-r`, then pipes the result to `uv add`:

```console
$ sed '/^-r /d' requirements-dev.in | uv add --dev -r - -c requirements-dev.txt
```

In addition to the `dev` dependency group, uv supports arbitrary group names. For example, if you
also have a dedicated set of dependencies for building your documentation, those can be imported to
a `docs` group:

```console
$ uv add -r requirements-docs.in -c requirements-docs.txt --group docs
```

#### Importing dependency sources

When importing requirements on local paths or Git repositories, for example:

```requirements title="requirements.in"
./path-dep
-e ./editable-path-dep
git-dep @ git+https://github.com/astral-sh/git-dep
```

uv will map them to [dependency sources](../../concepts/projects/dependencies.md#dependency-sources)
in the `[tool.uv.sources]` table of the `pyproject.toml`:

```toml title="pyproject.toml"
[project]
dependencies = [
    "path-dep",
    "editable-path-dep",
    "git-dep",
]

[tool.uv.sources]
path-dep = { path = "./path-dep" }
editable-path-dep = { path = "./editable-path-dep", editable = true }
git-dep = { git = "https://github.com/astral-sh/git-dep" }
```
```

</details>

## 20. `c8e18e33-76ed-5027-9e02-88255d44e8f7` (trap, ko)

**질문**: 제 pyproject.toml에는 여전히 `[tool.uv] dev-dependencies` 아래에 테스트 도구들이 나열되어 있습니다. `uv add --dev pytest`를 실행하면 uv는 pytest를 어디에 기록하며, 그 필드는 여전히 개발 의존성을 지정할 때 권장되는 위치인가요?

**답**:

```text
`uv add --dev pytest`는 pytest를 `[dependency-groups]` 테이블의 `dev` 그룹에 기록합니다. 이 명령은 `dev` 그룹을 만듭니다 [1]. 예시는 `dev = [ "pytest >=8.1.1,<9" ]` 형태입니다 [1].

개발 의존성을 선언할 때 uv가 사용하는 위치는 `[dependency-groups]` 테이블입니다(PEP 735 정의) [1]. 제공된 문서에는 `[tool.uv] dev-dependencies` 필드가 언급되어 있지 않으므로, 그 필드가 지금도 권장되는지 또는 더 이상 쓰지 않는지는 확인할 수 없습니다. 다만 문서 기준으로 개발 의존성의 위치는 `[dependency-groups]`입니다 [1].
```

**인용 판정 대상**(문장, 가리키는 근거 번호):

0. [1] 이 명령은 `dev` 그룹을 만듭니다 [1].
1. [1] 예시는 `dev = [ "pytest >=8.1.1,<9" ]` 형태입니다 [1].
2. [1] 개발 의존성을 선언할 때 uv가 사용하는 위치는 `[dependency-groups]` 테이블입니다(PEP 735 정의) [1].
3. [1] 다만 문서 기준으로 개발 의존성의 위치는 `[dependency-groups]`입니다 [1].

**핵심 요점**:

0. States that `uv add --dev` writes to the existing `tool.uv.dev-dependencies` section.
1. States that uv does not create a new `dependency-groups.dev` section in this case.
2. States that `tool.uv.dev-dependencies` is a legacy field that will eventually be deprecated and removed.
3. Identifies the `dev` group in `[dependency-groups]` as the recommended place.

**금지 내용**:

0. Claims `uv add --dev` always writes to `[dependency-groups]`.
1. Claims `tool.uv.dev-dependencies` is already removed or ignored.
2. Presents `tool.uv.dev-dependencies` as the currently recommended field.

<details><summary>근거 문서</summary>

**[1] concepts/projects/dependencies.md**

```text
## Development dependencies

Unlike optional dependencies, development dependencies are local-only and will _not_ be included in
the project requirements when published to PyPI or other indexes. As such, development dependencies
are not included in the `[project]` table.

Development dependencies can have entries in `tool.uv.sources` the same as normal dependencies.

To add a development dependency, use the `--dev` flag:

```console
$ uv add --dev pytest
```

uv uses the `[dependency-groups]` table (as defined in [PEP 735](https://peps.python.org/pep-0735/))
for declaration of development dependencies. The above command will create a `dev` group:

```toml title="pyproject.toml"
[dependency-groups]
dev = [
  "pytest >=8.1.1,<9"
]
```

The `dev` group is special-cased; there are `--dev`, `--only-dev`, and `--no-dev` flags to toggle
inclusion or exclusion of its dependencies. See `--no-default-groups` to disable all default groups
instead. Additionally, the `dev` group is [synced by default](#default-groups).
```

**[2] getting-started/features.md**

```text
# Features

uv provides essential features for Python development — from installing Python and hacking on simple
scripts to working on large projects that support multiple Python versions and platforms.

uv's interface can be broken down into sections, which are usable independently or together.

## Python versions

Installing and managing Python itself.

- `uv python install`: Install Python versions.
- `uv python list`: View available Python versions.
- `uv python find`: Find an installed Python version.
- `uv python pin`: Pin the current project to use a specific Python version.
- `uv python uninstall`: Uninstall a Python version.

See the [guide on installing Python](../guides/install-python.md) to get started.

## Scripts

Executing standalone Python scripts, e.g., `example.py`.

- `uv run`: Run a script.
- `uv add --script`: Add a dependency to a script.
- `uv remove --script`: Remove a dependency from a script.

See the [guide on running scripts](../guides/scripts.md) to get started.

## Projects

Creating and working on Python projects, i.e., with a `pyproject.toml`.

- `uv init`: Create a new Python project.
- `uv add`: Add a dependency to the project.
- `uv remove`: Remove a dependency from the project.
- `uv sync`: Sync the project's dependencies with the environment.
- `uv lock`: Create a lockfile for the project's dependencies.
- `uv run`: Run a command in the project environment.
- `uv tree`: View the dependency tree for the project.
- `uv build`: Build the project into distribution archives.
- `uv publish`: Publish the project to a package index.

See the [guide on projects](../guides/projects.md) to get started.

## Tools

Running and installing tools published to Python package indexes, e.g., `ruff` or `black`.

- `uvx` / `uv tool run`: Run a tool in a temporary environment.
- `uv tool install`: Install a tool user-wide.
- `uv tool uninstall`: Uninstall a tool.
- `uv tool list`: List installed tools.
- `uv tool update-shell`: Update the shell to include tool executables.

See the [guide on tools](../guides/tools.md) to get started.
```

**[3] guides/projects.md**

```text
### `pyproject.toml`

The `pyproject.toml` contains metadata about your project:

```toml title="pyproject.toml"
[project]
name = "hello-world"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
authors = [
  { name = "ferris", email = "ferris@example.org" }
]
requires-python = ">=3.14"
dependencies = []

[project.scripts]
hello-world = "hello_world:main"

[build-system]
requires = ["uv_build>=0.13.7,<0.14"]
build-backend = "uv_build"
```

You'll use this file to specify dependencies, as well as details about the project such as its
description or license. You can edit this file manually, or use commands like `uv add` and
`uv remove` to manage your project from the terminal.

!!! tip

    See the official [`pyproject.toml` guide](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)
    for more details on getting started with the `pyproject.toml` format.

You'll also use this file to specify uv [configuration options](../concepts/configuration-files.md)
in a [`[tool.uv]`](../reference/settings.md) section.

### `.python-version`

The `.python-version` file contains the project's default Python version. This file tells uv which
Python version to use when creating the project's virtual environment.

### `.venv`

The `.venv` folder contains your project's virtual environment, a Python environment that is
isolated from the rest of your system. This is where uv will install your project's dependencies.

See the [project environment](../concepts/projects/layout.md#the-project-environment) documentation
for more details.
```

**[4] concepts/projects/dependencies.md**

```text
# Managing dependencies

## Dependency fields

Dependencies of the project are defined in several fields:

- [`project.dependencies`](#project-dependencies): Published dependencies.
- [`project.optional-dependencies`](#optional-dependencies): Published optional dependencies, or
  "extras".
- [`dependency-groups`](#dependency-groups): Local dependencies for development.
- [`tool.uv.sources`](#dependency-sources): Alternative sources for dependencies during development.

!!! note

    The `project.dependencies` and `project.optional-dependencies` fields can be used even if
    the project isn't going to be published. `dependency-groups` are a recently standardized feature
    and may not be supported by all tools yet.

uv supports modifying the project's dependencies with `uv add` and `uv remove`, but dependency
metadata can also be updated by editing the `pyproject.toml` directly.
```

**[5] guides/migration/pip-to-project.md**

```text
#### Importing development dependency files

As discussed in the [development dependencies](#development-dependencies) section, it's common to
have groups of dependencies for development purposes.

To import development dependencies, use the `--dev` flag during `uv add`:

```console
$ uv add --dev -r requirements-dev.in -c requirements-dev.txt
```

If the `requirements-dev.in` includes the parent `requirements.in` via `-r`, it will need to be
stripped to avoid adding the base requirements to the `dev` dependency group. The following example
uses `sed` to strip lines that start with `-r`, then pipes the result to `uv add`:

```console
$ sed '/^-r /d' requirements-dev.in | uv add --dev -r - -c requirements-dev.txt
```

In addition to the `dev` dependency group, uv supports arbitrary group names. For example, if you
also have a dedicated set of dependencies for building your documentation, those can be imported to
a `docs` group:

```console
$ uv add -r requirements-docs.in -c requirements-docs.txt --group docs
```

#### Importing dependency sources

When importing requirements on local paths or Git repositories, for example:

```requirements title="requirements.in"
./path-dep
-e ./editable-path-dep
git-dep @ git+https://github.com/astral-sh/git-dep
```

uv will map them to [dependency sources](../../concepts/projects/dependencies.md#dependency-sources)
in the `[tool.uv.sources]` table of the `pyproject.toml`:

```toml title="pyproject.toml"
[project]
dependencies = [
    "path-dep",
    "editable-path-dep",
    "git-dep",
]

[tool.uv.sources]
path-dep = { path = "./path-dep" }
editable-path-dep = { path = "./editable-path-dep", editable = true }
git-dep = { git = "https://github.com/astral-sh/git-dep" }
```
```

</details>
