# test set 검수표 (40문항)

정본 `test_set.jsonl`, `test_set_ko.jsonl`에서 만든 표. (+)는 답이 반드시 담아야 할 요점, (-)는 답에 들어가면 틀린 답이 되는 내용이다.

## test-factual-01

- 근거 문서: concepts/python-versions.md
- Q: The only installed Python that matches my version request is a pre-release build. If a stable release of that version is available to download, will uv download and use the stable one instead?
- Q(ko): 요청한 버전에 맞는 설치된 Python이 프리릴리스 빌드뿐입니다. 해당 버전의 안정 릴리스를 다운로드할 수 있다면, uv가 대신 안정 릴리스를 다운로드해서 사용하나요?
- A: No. If a pre-release matches the request, uv uses it and does not download a stable version instead.
- (+) States that uv uses the matching pre-release.
- (+) States that uv does not download a stable version instead.
- (-) Claims uv downloads or prefers a stable version when an installed pre-release already matches the request.
- 메모: Replaced: the drafted question (uvx is shorthand for uv tool run) is general knowledge and does not need the documentation.

## test-factual-02

- 근거 문서: concepts/preview.md
- Q: What happens if I try to enable a uv preview feature that doesn't exist?
- Q(ko): 존재하지 않는 uv 프리뷰 기능을 활성화하려고 하면 어떻게 되나요?
- A: uv warns but does not error, regardless of the configuration source.
- (+) States that uv issues a warning.
- (+) States that uv does not error.
- (-) Claims that an unknown preview feature causes an error.

## test-factual-03

- 근거 문서: getting-started/installation.md
- Q: What happens when I install uv from PyPI on a platform without a prebuilt wheel?
- Q(ko): 미리 빌드된 휠이 없는 플랫폼에서 PyPI를 통해 uv를 설치하면 어떻게 되나요?
- A: uv is built from source, which requires a Rust toolchain.
- (+) Says uv is built from source.
- (+) Says a Rust toolchain is required.
- (-) Says installation cannot proceed on a platform without a prebuilt wheel.

## test-factual-04

- 근거 문서: guides/integration/coiled.md
- Q: What CPU and memory resources does a Coiled batch job's virtual machine have by default?
- Q(ko): Coiled 배치 작업의 가상 머신에는 기본적으로 CPU와 메모리 리소스가 얼마나 할당되나요?
- A: 4 CPU cores and 16 GiB of memory.
- (+) States that the default virtual machine has 4 cores.
- (+) States that it has 16 GiB of memory.

## test-factual-05

- 근거 문서: pip/environments.md
- Q: Which flag should I pass to uv pip install to target the system Python environment?
- Q(ko): 시스템 Python 환경을 대상으로 지정하려면 uv pip install에 어떤 플래그를 전달해야 하나요?
- A: `--system`
- (+) Identifies `--system` as the flag.
- (+) States that it targets the system Python environment.
- (-) Claims uv targets the system Python environment by default.

## test-factual-06

- 근거 문서: reference/policies/platforms.md
- Q: What is the minimum Windows Server version supported by uv?
- Q(ko): uv가 지원하는 최소 Windows Server 버전은 무엇인가요?
- A: Windows Server 2016.
- (+) Identifies Windows Server 2016.
- (+) States that it is the minimum supported Windows Server version.
- (-) Claims that an earlier Windows Server version is the minimum supported version.

## test-factual-07

- 근거 문서: concepts/projects/build.md
- Q: Which uv build flag requires hashes for all build dependencies, including transitive dependencies?
- Q(ko): 추이적 의존성을 포함한 모든 빌드 의존성에 해시를 요구하는 uv build 플래그는 무엇인가요?
- A: `--require-build-hashes`
- (+) Identifies `--require-build-hashes`.
- (+) Applies the requirement to transitive build dependencies.
- (-) Claims `--require-hashes` alone requires hashes for every transitive build dependency.

## test-factual-08

- 근거 문서: getting-started/features.md
- Q: Which uv command prints the directory where uv stores its installed Python versions?
- Q(ko): uv가 설치한 Python 버전을 저장하는 디렉터리를 출력하는 uv 명령어는 무엇인가요?
- A: `uv python dir`
- (+) Identifies `uv python dir` as the command.
- (+) States that it shows the path for uv's installed Python versions.
- (-) Claims `uv python list` prints the installed Python versions directory.

## test-factual-09

- 근거 문서: guides/integration/google.md
- Q: Which keyring provider mode does uv support for authenticating to Google Artifact Registry?
- Q(ko): Google Artifact Registry에 인증할 때 uv는 어떤 keyring 공급자 모드를 지원하나요?
- A: Subprocess mode.
- (+) Identifies subprocess mode.
- (+) States that subprocess is the only supported keyring mode.
- (-) Claims uv supports keyring in-process mode.

## test-factual-10

- 근거 문서: pip/compile.md
- Q: If I run `uv pip compile some/path/pyproject.toml --group foo`, which file does uv use to find the `foo` dependency group?
- Q(ko): `uv pip compile some/path/pyproject.toml --group foo`를 실행하면 uv는 `foo` 의존성 그룹을 찾기 위해 어떤 파일을 사용하나요?
- A: It uses `./pyproject.toml` in the current directory.
- (+) Identifies `./pyproject.toml` as the source of the group.
- (+) Makes clear that the file is in the current directory.
- (-) Claims the group is sourced from `some/path/pyproject.toml`.

## test-factual-11

- 근거 문서: reference/storage.md
- Q: Which environment variable can I set to change where uv installs managed Python versions?
- Q(ko): uv가 관리하는 Python 버전의 설치 위치를 바꾸려면 어떤 환경 변수를 설정하면 되나요?
- A: UV_PYTHON_INSTALL_DIR
- (+) Names `UV_PYTHON_INSTALL_DIR`.
- (+) Identifies it as controlling the Python installation directory.
- (-) Claims `UV_PYTHON_BIN_DIR` changes the managed Python installation directory.

## test-factual-12

- 근거 문서: concepts/resolution.md
- Q: If I both exclude and override the same dependency in the same scope in uv, which setting wins?
- Q(ko): uv에서 같은 스코프의 동일한 의존성을 제외하면서 동시에 오버라이드하면 어떤 설정이 우선하나요?
- A: The exclusion takes precedence.
- (+) States that the exclusion takes precedence.
- (+) Indicates that the matching dependency is excluded rather than overridden.
- (-) Claims that the override takes precedence.

## test-multi_doc-01 [추론]

- 근거 문서: reference/policies/versioning.md, concepts/cache.md
- Q: If I upgrade uv with only a patch-version change, can both its cache format and uv.lock schema change, and can the old and new versions still safely use the same cache directory?
- Q(ko): uv를 패치 버전만 바뀌도록 업그레이드해도 캐시 형식과 uv.lock 스키마가 둘 다 바뀔 수 있나요? 그리고 이전 버전과 새 버전이 같은 캐시 디렉터리를 안전하게 사용할 수 있나요?
- A: A patch release can change the cache format, but not the uv.lock schema version. Both uv versions can safely share a cache directory, though they may not share all cache entries.
- (+) States that the cache format can change in a patch release.
- (+) States that the uv.lock schema version cannot be incremented in a patch release.
- (+) States that the old and new uv versions can safely share a cache directory.
- (+) Notes that a cache version change may prevent sharing some underlying entries.
- (-) Claims that a patch release can increment the uv.lock schema version.
- (-) Claims that sharing a cache directory between the two uv versions is unsafe.
- (-) Claims that both versions are guaranteed to share every cache entry.

## test-multi_doc-02 [추론]

- 근거 문서: concepts/indexes.md, guides/integration/aws.md
- Q: My uv index for AWS CodeArtifact has `authenticate = "never"`. Can I authenticate by putting credentials in its URL? If not, what should I change, and what username and password should I use?
- Q(ko): AWS CodeArtifact용 uv 인덱스에 `authenticate = "never"`가 설정되어 있습니다. URL에 인증 정보를 넣어서 인증할 수 있나요? 안 된다면 무엇을 변경해야 하고, 사용자 이름과 비밀번호는 무엇을 사용해야 하나요?
- A: No. Remove `authenticate = "never"`, then use `aws` as the URL username and the CodeArtifact access token as the password.
- (+) States that credentials in the URL will cause an error with `authenticate = "never"`.
- (+) Says to remove or change the `never` authentication setting.
- (+) Specifies `aws` as the username.
- (+) Specifies the CodeArtifact access token as the password.
- (-) Claims that `authenticate = "never"` allows credentials embedded in the index URL.
- (-) Suggests a username other than `aws` for CodeArtifact authentication.

## test-multi_doc-03 [추론]

- 근거 문서: guides/package.md, guides/integration/azure.md
- Q: My CI job has built distributions but no project checkout or `pyproject.toml`. Can I publish to Azure Artifacts with `uv publish --index private-registry`? What is the tradeoff if I instead set `UV_PUBLISH_URL` to the Azure upload endpoint and run `uv publish`?
- Q(ko): CI 작업에 빌드된 배포 파일은 있지만 프로젝트 체크아웃이나 `pyproject.toml`은 없습니다. `uv publish --index private-registry`로 Azure Artifacts에 게시할 수 있나요? 대신 `UV_PUBLISH_URL`을 Azure 업로드 엔드포인트로 설정하고 `uv publish`를 실행하면 어떤 장단점이 있나요?
- A: No. Publishing with `--index` requires `pyproject.toml`. Using `UV_PUBLISH_URL` avoids that requirement, but uv cannot check whether the package is already published before uploading.
- (+) States that publishing with `--index private-registry` requires `pyproject.toml`.
- (+) Identifies `UV_PUBLISH_URL` with `uv publish` as an alternative.
- (+) States that this alternative cannot check whether the package is already published before uploading.
- (-) Claims that `uv publish --index private-registry` works without `pyproject.toml`.
- (-) Claims that setting only `UV_PUBLISH_URL` lets uv check whether the package is already published before uploading.

## test-multi_doc-04 [추론]

- 근거 문서: reference/troubleshooting/reproducible-examples.md, guides/integration/docker.md
- Q: I'm sharing a Docker reproducer for a Linux issue on ARM64. Is `FROM --platform=linux/arm64 ghcr.io/astral-sh/uv:0.13.7-debian-slim` enough to select the architecture and ensure the same base image is used in future rebuilds? If not, what should I change?
- Q(ko): ARM64의 Linux 문제를 재현하는 Docker 환경을 공유하려고 합니다. `FROM --platform=linux/arm64 ghcr.io/astral-sh/uv:0.13.7-debian-slim`만으로 아키텍처를 선택하고 나중에 다시 빌드할 때도 같은 베이스 이미지가 사용되도록 보장할 수 있나요? 안 된다면 무엇을 변경해야 하나요?
- A: The platform flag selects ARM64, but the version tag can move. Keep the platform flag and pin the desired image by its SHA256 digest instead of relying on the tag.
- (+) Says the platform flag selects Linux ARM64.
- (+) Says the version tag alone does not guarantee an immutable image because tags can move.
- (+) Recommends pinning the desired image by SHA256 digest while retaining the platform selection.
- (-) Claims a specific version tag guarantees the same image in future rebuilds.
- (-) Claims the platform flag alone pins the image contents.

## test-multi_doc-05

- 근거 문서: concepts/projects/config.md, guides/integration/pytorch.md
- Q: My uv project already depends on torch and cchardet. I want CUDA 13.0 PyTorch on Linux and CPU-only PyTorch elsewhere, and cchardet needs Cython to build even though it doesn't declare it. How should I configure pyproject.toml without turning off build isolation?
- Q(ko): 제 uv 프로젝트는 이미 torch와 cchardet에 의존하고 있습니다. Linux에서는 CUDA 13.0 PyTorch를, 그 외 환경에서는 CPU 전용 PyTorch를 사용하고 싶습니다. 또한 cchardet은 빌드할 때 Cython이 필요하지만 이를 의존성으로 선언하지 않습니다. 빌드 격리를 끄지 않고 pyproject.toml을 어떻게 설정해야 하나요?
- A: Add these settings to pyproject.toml:  ```toml [tool.uv.extra-build-dependencies] cchardet = ["cython"]  [tool.uv.sources] torch = [   { index = "pytorch-cu130", marker = "sys_platform == 'linux'" },   { index = "pytorch-cpu", marker = "sys_platform != 'linux'" }, ]  [[tool.uv.index]] name = "pytorch-cu130" url = "https://download.pytorch.org/whl/cu130" explicit = true  [[tool.uv.index]] name = "pytorch-cpu" url = "https://download.pytorch.org/whl/cpu" explicit = true ```
- (+) Adds cython as an extra build dependency for cchardet without disabling build isolation.
- (+) Selects the CUDA 13.0 index for torch on Linux and the CPU index on other platforms using source markers.
- (+) Defines the CUDA index at https://download.pytorch.org/whl/cu130.
- (+) Defines the CPU index at https://download.pytorch.org/whl/cpu.
- (-) Disables build isolation for cchardet.
- (-) Selects the CUDA index on all platforms or the CPU index on Linux.

## test-multi_doc-06

- 근거 문서: getting-started/features.md, guides/install-python.md
- Q: How can I install the latest Python with both `python` and `python3` executables, then view my project's dependency tree with uv? Is the install option stable?
- Q(ko): 최신 Python을 `python`과 `python3` 실행 파일이 모두 포함되도록 설치한 다음, uv로 프로젝트의 의존성 트리를 보려면 어떻게 해야 하나요? 이 설치 옵션은 안정적인가요?
- A: Run `uv python install --default`, then `uv tree`. The `--default` option is experimental.
- (+) Uses `uv python install --default` to install Python with the requested executables.
- (+) Uses `uv tree` to view the project's dependency tree.
- (+) Identifies `--default` as experimental.
- (-) Claims that `python` and `python3` are installed by default without `--default`.
- (-) Presents `--default` as stable.

## test-multi_doc-07

- 근거 문서: guides/integration/marimo.md, guides/scripts.md
- Q: I have a marimo notebook named `my_notebook.py` with PEP 723 metadata. How do I lock its dependencies with uv, what file will that create, and how can I run the notebook without opening a browser?
- Q(ko): PEP 723 메타데이터가 포함된 `my_notebook.py`라는 marimo 노트북이 있습니다. uv로 이 노트북의 의존성을 잠그려면 어떻게 해야 하고, 그러면 어떤 파일이 생성되나요? 또 브라우저를 열지 않고 노트북을 실행하려면 어떻게 해야 하나요?
- A: Run `uv lock --script my_notebook.py` to create `my_notebook.py.lock` alongside the notebook. Then run `uv run my_notebook.py` to execute it as a script without opening a browser.
- (+) Gives `uv lock --script my_notebook.py` as the locking command.
- (+) Identifies `my_notebook.py.lock` alongside the notebook as the created file.
- (+) Gives `uv run my_notebook.py` as the command to execute the notebook without a browser.
- (-) Claims that running the notebook automatically creates its script lockfile.
- (-) Claims that script execution opens an interactive browser session.

## test-multi_doc-08

- 근거 문서: guides/integration/fastapi.md, concepts/projects/init.md
- Q: I have an existing FastAPI app in `project/app` and want to keep it unpackaged instead of using uv's default application layout. What commands should I run from `project` to set it up with FastAPI's standard extras and start the development server? How does this differ from the default uv application setup?
- Q(ko): `project/app`에 기존 FastAPI 앱이 있는데, uv의 기본 애플리케이션 레이아웃을 사용하는 대신 패키지화하지 않은 상태로 유지하고 싶습니다. `project`에서 어떤 명령을 실행해야 FastAPI의 standard extras를 포함해 설정하고 개발 서버를 시작할 수 있나요? 이 방식은 기본 uv 애플리케이션 설정과 어떻게 다른가요?
- A: Run `uv init --no-package`, `uv add fastapi --extra standard`, and `uv run fastapi dev`. Unlike the default application setup, which defines a build system and uses a `src` layout, the unpackaged project has no build system and is not installed into the environment.
- (+) Says to run `uv init --no-package` from the project directory.
- (+) Says to run `uv add fastapi --extra standard`.
- (+) Says to start the development server with `uv run fastapi dev`.
- (+) Explains that the default application setup defines a build system and uses a `src` layout.
- (+) Explains that the unpackaged project has no build system and is not installed into the environment.
- (-) Claims the `--no-package` project is installed into the environment.
- (-) Claims the default application setup has no build system.

## test-multi_doc-09

- 근거 문서: guides/projects.md, concepts/projects/export.md
- Q: How can I update only requests to its latest compatible version, without updating other locked packages, and then export a PEP 751 lockfile to the existing release directory with local paths relative to that directory?
- Q(ko): 잠긴 다른 패키지는 업데이트하지 않고 requests만 호환되는 최신 버전으로 업데이트한 다음, 로컬 경로를 기존 release 디렉터리 기준 상대 경로로 하여 PEP 751 lockfile을 그 디렉터리에 내보내려면 어떻게 해야 하나요?
- A: Run `uv lock --upgrade-package requests`, then `uv export --format pylock.toml --output-file release/pylock.toml`.
- (+) Uses `uv lock --upgrade-package requests` to update requests.
- (+) Exports using `uv export` with `--format pylock.toml`.
- (+) Uses `--output-file release/pylock.toml` or an equivalent path in the release directory.
- (+) Places the upgrade before the export.
- (-) Claims the upgrade updates all packages rather than targeting requests.
- (-) Exports to stdout while claiming local paths will be relative to the release directory.

## test-multi_doc-10

- 근거 문서: reference/internals/resolver.md, concepts/resolution.md
- Q: My uv.lock contains different versions of a dependency for different Python versions. How does uv keep the split boundaries stable when re-resolving, and how can I favor using one version across Python versions when possible?
- Q(ko): 제 uv.lock에는 Python 버전에 따라 하나의 의존성에 서로 다른 버전이 들어 있습니다. uv는 의존성을 다시 해석할 때 버전 분기 경계를 어떻게 안정적으로 유지하나요? 그리고 가능하면 여러 Python 버전에서 하나의 버전을 사용하도록 우선하려면 어떻게 해야 하나요?
- A: uv saves the fork resolution markers in the lockfile and reuses them on re-resolution. Use `--fork-strategy fewest` to minimize the number of selected versions, preferring versions compatible with a wider range of Python versions.
- (+) States that uv records fork resolution markers in the lockfile and reuses the saved forks.
- (+) Recommends `--fork-strategy fewest`.
- (+) Explains that the strategy minimizes selected versions and can favor older versions with broader compatibility.
- (-) Claims that `--fork-strategy fewest` guarantees a single version in every resolution.
- (-) Claims uv always recomputes fork boundaries from scratch without using the lockfile.

## test-summary-01

- 근거 문서: guides/package.md
- Q: How does publishing a Python package with uv work, including authentication, custom indexes, retries, and attestations?
- Q(ko): uv로 Python 패키지를 게시하는 과정은 어떻게 동작하나요? 인증, 커스텀 인덱스, 재시도, attestations도 포함해서 설명해 주세요.
- A: 1. Run `uv publish`; authenticate to PyPI with a token or configure a trusted publisher. 2. For a custom index, configure `publish-url` and use `uv publish --index <name>`. 3. After a partial upload, retry the same command for PyPI; for other registries, use `--check-url` with the index URL. 4. uv automatically discovers and uploads matching attestations to registries that support them.
- (+) Identifies `uv publish` as the publishing command and describes PyPI token or trusted-publisher authentication.
- (+) Explains that a custom index needs `publish-url` and `uv publish --index <name>`.
- (+) Explains how to retry a partial PyPI upload and use `--check-url` with other registries.
- (+) States that uv discovers and uploads matching attestations to supported registries.
- (-) Claims PyPI accepts ordinary username-and-password publishing.
- (-) Claims uv generates attestations during publishing.
- (-) Says `--check-url` should point to the publishing URL rather than the index URL.

## test-summary-02

- 근거 문서: concepts/projects/dependencies.md
- Q: How does uv handle development dependency groups, including publication, adding groups, resolution, and default inclusion?
- Q(ko): uv는 개발 의존성 그룹을 어떻게 처리하나요? 게시, 그룹 추가, 의존성 해석, 기본 포함 여부도 포함해서 설명해 주세요.
- A: 1. Development dependencies are local-only and are not published as project requirements; uv declares them in `[dependency-groups]`. 2. Use `uv add --dev` for the `dev` group or `uv add --group <name>` for another group. 3. uv resolves all groups together, so they must be compatible unless conflicts are explicitly declared. 4. The `dev` group is included by default; `tool.uv.default-groups` can change the defaults.
- (+) States that development dependencies are local-only, not published requirements, and are declared in dependency groups.
- (+) Explains how to add dependencies to the dev group and to another named group.
- (+) States that all groups are resolved together and must be compatible unless conflicts are explicitly declared.
- (+) States that dev is included by default and the default groups are configurable.
- (-) Claims development dependency groups are published as project requirements.
- (-) Claims uv resolves each dependency group independently.

## test-summary-03

- 근거 문서: pip/environments.md
- Q: How does uv choose a Python environment for package installation, and how can I select a different one?
- Q(ko): uv는 패키지를 설치할 Python 환경을 어떻게 선택하며, 다른 환경을 선택하려면 어떻게 해야 하나요?
- A: 1. uv requires a virtual environment by default. 2. It searches for an active `VIRTUAL_ENV`, then an active Conda environment, then a nearby `.venv`; if none is found, it prompts you to create one. 3. `VIRTUAL_ENV` must point to a PEP 405-compliant environment. 4. `--python` can target a specific interpreter or virtual-environment root, including a non-virtual environment. 5. `--system` targets system Python and opts into modifying system environments when requesting an interpreter by version.
- (+) States that uv requires a virtual environment by default.
- (+) Gives the discovery order: `VIRTUAL_ENV`, `CONDA_PREFIX`, then `.venv` in the current or nearest parent directory, and notes the creation prompt if none is found.
- (+) Explains that `--python` can select an interpreter or virtual-environment root, including a non-virtual environment.
- (+) Explains that `--system` targets system Python and permits system-interpreter selection when requesting a Python version.
- (-) Claims uv installs into system Python by default.
- (-) Claims an active Conda environment takes precedence over `VIRTUAL_ENV`.
- (-) Claims `--python` can only target virtual environments.

## test-summary-04

- 근거 문서: concepts/python-versions.md
- Q: How does upgrading uv-managed Python versions work, and what are its limits?
- Q(ko): uv가 관리하는 Python 버전의 업그레이드는 어떻게 동작하며, 어떤 한계가 있나요?
- A: 1. Only uv-managed Python versions can be upgraded, and only to the latest patch release; uv does not upgrade across minor versions because that can affect dependency resolution. 2. Run `uv python upgrade 3.12` for one version or `uv python upgrade` for all installed versions. 3. The previous patch version is kept and the new one is preferred. 4. Virtual environments using that version are upgraded automatically, except ones created with an explicit patch version such as `uv venv -p 3.10.8`. 5. Automatic upgrades rely on a minor-version link; if another tool resolves that link to create an environment, that environment is not upgraded.
- (+) States that only uv-managed Python versions can be upgraded.
- (+) States that upgrades go to the latest patch release and not across minor versions.
- (+) Gives `uv python upgrade` (for one version or all) as the command.
- (+) States that the previous version is retained and the new one is preferred.
- (+) States that virtual environments are upgraded automatically, except ones created with an explicit patch version.
- (-) Claims uv upgrades across minor versions, e.g. 3.12 to 3.13.
- (-) Claims the previous patch version is removed after an upgrade.
- (-) Claims PyPy, GraalPy or Pyodide versions can be upgraded the same way.
- 메모: Replaced: the drafted question (uv's main capabilities) is answerable from general knowledge.

## test-summary-05

- 근거 문서: guides/integration/pytorch.md
- Q: How does uv's PyTorch backend selection work, and where can I use it?
- Q(ko): uv의 PyTorch 백엔드 선택 기능은 어떻게 동작하며, 어디에서 사용할 수 있나요?
- A: 1. Enable automatic selection with `--torch-backend=auto` or `UV_TORCH_BACKEND=auto`. 2. uv checks for CUDA, AMD, and Intel GPU support, chooses a compatible PyTorch index, and falls back to the CPU-only index if no supported GPU is found. Other packages retain their existing index configuration. 3. A specific backend can be selected instead, for example with `--torch-backend=cu130`. 4. Backend selection is currently available only through `uv pip`.
- (+) Identifies the command-line flag or environment variable for automatic selection.
- (+) Explains GPU detection, compatible index selection, and CPU-only fallback.
- (+) States that existing index configuration is preserved for packages outside the PyTorch ecosystem.
- (+) Notes that a specific backend can be selected and that backend selection is currently limited to `uv pip`.
- (-) Claims automatic selection always uses a GPU index even when no supported GPU is found.
- (-) Claims `--torch-backend` is currently available in uv's project interface.

## test-summary-06

- 근거 문서: reference/storage.md
- Q: How does uv's dependency cache work, and what should I know about its location and performance?
- Q(ko): uv의 의존성 캐시는 어떻게 동작하며, 캐시 위치와 성능에 대해 무엇을 알아야 하나요?
- A: uv caches dependencies locally to avoid downloading and building them again. It uses the cache directory by default, but the location can be overridden through command-line arguments, environment variables, or settings; when caching is disabled, it uses a temporary directory. Run `uv cache dir` to see the current path. For optimal performance, keep the cache on the same filesystem as virtual environments.
- (+) States that the cache avoids re-downloading and re-building dependencies.
- (+) Explains the default location, available override methods, and use of a temporary directory when caching is disabled.
- (+) Identifies `uv cache dir` as the command to show the current cache path.
- (+) States that the cache should be on the same filesystem as virtual environments for optimal performance.
- (-) Claims that disabling the cache means uv uses no temporary cache.
- (-) Claims that the cache must be on a different filesystem from virtual environments for optimal performance.

## test-trap-01

- 근거 문서: guides/integration/pre-commit.md
- Q: In the official uv pre-commit integration, how should I configure a hook to compile requirements-dev.in into requirements-dev.txt and match changes to either file?
- Q(ko): 공식 uv pre-commit 연동에서 requirements-dev.in을 requirements-dev.txt로 컴파일하고 두 파일 중 어느 쪽의 변경도 감지하도록 훅을 구성하려면 어떻게 해야 하나요?
- A: Use hook ID `pip-compile` with `args: [requirements-dev.in, -o, requirements-dev.txt]` and `files: ^requirements-dev\.(in|txt)$`.
- (+) Uses the hook ID `pip-compile`.
- (+) Specifies arguments `requirements-dev.in`, `-o`, and `requirements-dev.txt` in that order.
- (+) Uses `files: ^requirements-dev\.(in|txt)$` or an equivalent pattern matching both files.
- (-) Uses `uv-pip-compile` as the hook ID.

## test-trap-02

- 근거 문서: concepts/projects/workspaces.md
- Q: In a uv workspace, the root configures a Git source for a dependency, but one member configures its own source for that dependency with a Windows-only marker. When resolving that member on Linux, does uv fall back to the root's Git source?
- Q(ko): uv 워크스페이스의 루트에서 한 의존성의 Git 소스를 설정했는데, 한 멤버가 같은 의존성에 대해 Windows 전용 마커가 붙은 자체 소스를 설정했습니다. Linux에서 해당 멤버의 의존성을 해결할 때 uv는 루트의 Git 소스로 대체하나요?
- A: No. The member's source entry overrides the root's entry even when its marker does not match the current platform.
- (+) States that uv does not fall back to the root's Git source.
- (+) Explains that the member's source entry overrides the root entry even when its marker does not match.
- (-) Claims that a nonmatching member marker causes uv to use the workspace root's source.

## test-trap-03

- 근거 문서: guides/tools.md
- Q: On Windows, if I invoke a legacy tool script with uvx without specifying its file extension, which extensions are checked, and in what order?
- Q(ko): Windows에서 uvx로 레거시 도구 스크립트를 실행할 때 파일 확장자를 지정하지 않으면 어떤 확장자를 어떤 순서로 확인하나요?
- A: uvx checks `.ps1`, then `.cmd`, then `.bat`.
- (+) Says `.ps1` is checked first.
- (+) Says `.cmd` is checked second.
- (+) Says `.bat` is checked third.
- (-) Claims that the extension must be specified.
- (-) Gives a different search order.

## test-trap-04

- 근거 문서: concepts/projects/dependencies.md
- Q: My pyproject.toml still lists test tools under `[tool.uv] dev-dependencies`. If I run `uv add --dev pytest`, where does uv record pytest, and is that field still the recommended place for development dependencies?
- Q(ko): 제 pyproject.toml에는 여전히 `[tool.uv] dev-dependencies` 아래에 테스트 도구들이 나열되어 있습니다. `uv add --dev pytest`를 실행하면 uv는 pytest를 어디에 기록하며, 그 필드는 여전히 개발 의존성을 지정할 때 권장되는 위치인가요?
- A: uv adds pytest to the existing `tool.uv.dev-dependencies` section instead of creating a `dependency-groups.dev` section. The field is legacy: its entries are combined with `dependency-groups.dev`, and it will eventually be deprecated and removed, so `[dependency-groups]` is the recommended place.
- (+) States that `uv add --dev` writes to the existing `tool.uv.dev-dependencies` section.
- (+) States that uv does not create a new `dependency-groups.dev` section in this case.
- (+) States that `tool.uv.dev-dependencies` is a legacy field that will eventually be deprecated and removed.
- (+) Identifies the `dev` group in `[dependency-groups]` as the recommended place.
- (-) Claims `uv add --dev` always writes to `[dependency-groups]`.
- (-) Claims `tool.uv.dev-dependencies` is already removed or ignored.
- (-) Presents `tool.uv.dev-dependencies` as the currently recommended field.
- 메모: Replaced: the drafted question duplicated the multi_doc item on `uv lock --upgrade-package` and had no trap. The trap is that uv add --dev keeps writing to the legacy field.

## test-unanswerable-01

- 근거 문서: 없음
- Q: In Poetry 2.1.0, which source-code function decides the next dependency to resolve, and how does its priority calculation differ from uv's?
- Q(ko): Poetry 2.1.0에서 다음에 해결할 의존성을 결정하는 소스 코드 함수는 무엇이며, 그 함수의 우선순위 계산 방식은 uv와 어떻게 다른가요?
- A: (답 없음)
- (+) States that the documentation does not cover this and does not invent an answer.
- (-) Names a Poetry function or describes its priority formula as though verified from the uv documentation.
- 메모: The outline covers uv's resolver internals, but not Poetry's version-specific source code.

## test-unanswerable-02

- 근거 문서: 없음
- Q: What compiler version and complete compiler flags were used to build the downloadable CPython 3.12.8 Linux x86-64 binary that uv installs?
- Q(ko): uv가 설치하는 다운로드 가능한 CPython 3.12.8 Linux x86-64 바이너리를 빌드할 때 사용된 컴파일러 버전과 전체 컴파일러 플래그는 무엇인가요?
- A: (답 없음)
- (+) States that the documentation does not cover this and does not invent an answer.
- (-) Invents a GCC or Clang version and a list of flags for that binary.
- 메모: The Python installation documentation is not an artifact-specific build manifest for the externally produced interpreter.

## test-unanswerable-03

- 근거 문서: 없음
- Q: For a 500-dependency project built on a GitHub-hosted ubuntu-latest runner, how many seconds does a warm uv cache save compared with a cold cache?
- Q(ko): GitHub에서 호스팅하는 ubuntu-latest 러너에서 의존성이 500개인 프로젝트를 빌드할 때, uv 캐시가 채워져 있으면 비어 있을 때보다 몇 초가 절약되나요?
- A: (답 없음)
- (+) States that the documentation does not cover this and does not invent an answer.
- (-) Gives a numerical time saving as a documented benchmark for the specified setup.
- 메모: The documentation covers caching and benchmarks, but does not provide a measurement for this particular project and runner.

## test-unanswerable-04

- 근거 문서: 없음
- Q: What contractual detection-latency SLA does uv's malware-checking data provider offer enterprise customers after a malicious package is reported?
- Q(ko): uv의 악성코드 검사 데이터 제공업체는 악성 패키지가 신고된 후 탐지되기까지의 지연 시간에 대해 기업 고객에게 어떤 계약상 SLA를 제공하나요?
- A: (답 없음)
- (+) States that the documentation does not cover this and does not invent an answer.
- (-) Claims a guaranteed detection time or asserts that a particular SLA applies without an authoritative contract.
- 메모: The outline mentions malware checks, not the provider's enterprise contract terms or detection SLA.

## test-unanswerable-05

- 근거 문서: 없음
- Q: Which uv release will make the workspace metadata schema stable, and what date have the maintainers committed to for that release?
- Q(ko): 어느 uv 릴리스에서 워크스페이스 메타데이터 스키마가 안정화되며, 유지관리자들이 약속한 해당 릴리스 날짜는 언제인가요?
- A: (답 없음)
- (+) States that the documentation does not cover this and does not invent an answer.
- (-) Invents a uv release number or a maintainer-committed date.
- 메모: The outline documents workspace metadata and versioning, not a committed future release date for schema stabilization.

## test-unanswerable-06

- 근거 문서: 없음
- Q: In the VS Code Jupyter extension's source code, which function selects a kernel when I open a notebook in a uv-managed project?
- Q(ko): VS Code Jupyter 확장의 소스 코드에서 uv로 관리하는 프로젝트의 노트북을 열 때 커널을 선택하는 함수는 무엇인가요?
- A: (답 없음)
- (+) States that the documentation does not cover this and does not invent an answer.
- (-) Invents or presents an unverified extension function name as the kernel-selection implementation.
- 메모: The Jupyter guide covers using VS Code with a uv project, not the extension's implementation.

## test-unanswerable-07

- 근거 문서: 없음
- Q: How do I configure an AWS CodeArtifact repository to retain only the latest ten versions of each package automatically?
- Q(ko): AWS CodeArtifact 리포지토리에서 각 패키지의 최신 버전 10개만 자동으로 유지하도록 설정하려면 어떻게 해야 하나요?
- A: (답 없음)
- (+) States that the documentation does not cover this and does not invent an answer.
- (-) Invents an AWS CLI command or CodeArtifact setting that supposedly enables that retention policy.
- 메모: The CodeArtifact integration guide covers authentication and publishing, not repository retention administration.

## test-unanswerable-08

- 근거 문서: 없음
- Q: How do I configure an S3 lifecycle rule to delete archived CI cache objects after 30 days?
- Q(ko): 아카이브된 CI 캐시 객체를 30일 후에 삭제하도록 S3 수명 주기 규칙을 설정하려면 어떻게 해야 하나요?
- A: (답 없음)
- (+) States that the documentation does not cover this and does not invent an answer.
- (-) Presents an invented S3 configuration as something specified by the uv documentation.
- 메모: The documentation discusses caching in CI, but the outline does not describe administering S3 lifecycle rules.
