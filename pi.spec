# Pi coding agent. The CLI is an esbuild bundle of the TypeScript
# monorepo. npm dependencies are vendored because the builders have no
# network. esbuild and the X11 clipboard helper are compiled here.
# Prebuilt .node/.wasm/.so files from npm and the git tree are deleted.
#
# debugedit cannot split Go's DWARF, and the clipboard helper is
# stripped by its own link line. There is no useful debuginfo.
%global debug_package %{nil}
#
# Not built:
# - @silvia-odwyer/photon-node (wasm, no source in the npm package)
# - quickjs-wasi (quickjs.wasm and extension objects, no source)
# fd is not packaged. Pi warns instead of downloading a GitHub binary.

%ifarch aarch64
%define esbuild_cpu arm64
%else
%define esbuild_cpu x64
%endif

Name:		pi
Version:	1.1.0
Release:	1
Summary:	Minimal, extensible agent harness
Group:		Development/Other
License:	MIT
URL:		https://github.com/earendil-works/pi
Source0:	https://github.com/earendil-works/pi/archive/refs/tags/v%{version}.tar.gz
# npm ci --ignore-scripts. Includes packages/*/node_modules, where npm
# nests copies that are not the hoisted version. Prebuilt natives removed.
Source1:	pi-%{version}-node_modules.tar.xz
# packages/ai/src/providers/data snapshot. Upstream gitignores this tree.
Source2:	pi-%{version}-model-data.tar.xz
# esbuild 0.28.2 Go sources and vendor. This release pins that version.
Source3:	esbuild-0.28.2-with-vendor.tar.xz
# Do not download ripgrep or fd release binaries at runtime.
Patch0:		pi-no-tool-download.patch

BuildRequires:	nodejs
BuildRequires:	golang
BuildRequires:	typescript
BuildRequires:	pkgconfig(xcb)
BuildRequires:	file

Requires:	nodejs >= 22.19.0
Requires:	git
Requires:	rg
Requires:	xclip
Requires:	wl-clipboard

%description
Pi is a terminal agent harness. It talks to an LLM provider and edits
a project from the command line, with extensions, skills, and themes.

This package builds the Node.js CLI from source. esbuild and the X11
clipboard helper are compiled here. Prebuilt npm native addons and
WebAssembly are not shipped.

Photon image transcoding and the QuickJS codemode sandbox are not
available: those npm packages publish WebAssembly without source that
can be rebuilt. File search wants fd, which is not packaged; Pi says
so instead of downloading a binary. Code search uses system rg.

%prep
%autosetup -n pi-%{version} -p1 -a 1

mkdir -p packages/ai/src/providers
tar -xf %{SOURCE2} -C packages/ai/src/providers
tar -xf %{SOURCE3}

# The npm typescript bin execs a prebuilt compiler. Use the system one.
rm -f node_modules/.bin/tsc
printf '%s\n' '#!/bin/sh' 'exec /usr/bin/tsc "$@"' > node_modules/.bin/tsc
chmod 0755 node_modules/.bin/tsc

find node_modules packages -type f \( \
	-name '*.node' -o \
	-name '*.wasm' -o \
	-name '*.so' -o \
	-name '*.dll' -o \
	-name '*.exe' -o \
	-name '*.dylib' -o \
	-name 'esbuild' \
	\) -delete
find node_modules packages -type f \
	! -name '*.js' ! -name '*.mjs' ! -name '*.cjs' ! -name '*.ts' ! -name '*.tsx' \
	! -name '*.json' ! -name '*.md' ! -name '*.map' ! -name '*.txt' ! -name '*.yml' \
	! -name '*.yaml' ! -name '*.html' ! -name '*.css' ! -name '*.c' ! -name '*.h' \
	! -name '*.png' ! -name '*.svg' \
	-print0 | xargs -0 -r file -N | \
	awk -F': ' '$2 ~ /^(ELF|PE32|Mach-O|MS-DOS)/ { print $1 }' | \
	xargs -r rm -f

%build
export HOME="$(mktemp -d)"
export npm_config_offline=true
export npm_config_ignore_scripts=true
export npm_config_update_notifier=false
export GIT_TERMINAL_PROMPT=0
export GIT_CONFIG_GLOBAL=/dev/null
export GIT_CONFIG_NOSYSTEM=1
export GOTOOLCHAIN=local
export GOPROXY=off
export GOFLAGS=-mod=vendor
export ESBUILD_BINARY_PATH="$PWD/esbuild-bin"

(
	cd esbuild-0.28.2
	go build -mod=vendor -ldflags '-s -w' -o "$ESBUILD_BINARY_PATH" ./cmd/esbuild
)
test -x "$ESBUILD_BINARY_PATH"
"$ESBUILD_BINARY_PATH" --version | grep -qx '0.28.2'

npm --prefix packages/tui run build:native:linux
npm run build:offline

%install
lib="%{buildroot}%{_libdir}/pi"
agent="$lib/node_modules/@earendil-works/pi-coding-agent"
mods="$lib/node_modules"
mkdir -p "$agent/dist/modes/interactive" "$agent/dist/core" \
	"$mods/@earendil-works/chord" \
	"$mods/@earendil-works/pi-tui/native/linux" \
	"$mods/@esbuild/linux-%{esbuild_cpu}/bin" \
	"%{buildroot}%{_bindir}"

install -m0644 packages/coding-agent/package.json "$agent/package.json"
install -m0644 packages/coding-agent/README.md "$agent/README.md"
install -m0644 packages/coding-agent/CHANGELOG.md "$agent/CHANGELOG.md"
cp -a packages/coding-agent/docs "$agent/docs"
cp -a packages/coding-agent/examples "$agent/examples"
cp -a packages/coding-agent/dist/bundle "$agent/dist/bundle"
cp -a packages/coding-agent/dist/modes/interactive/theme "$agent/dist/modes/interactive/theme"
cp -a packages/coding-agent/dist/modes/interactive/assets "$agent/dist/modes/interactive/assets"
cp -a packages/coding-agent/dist/core/export-html "$agent/dist/core/export-html"
chmod 0755 "$agent/dist/bundle/cli.js"

cp -a node_modules/jiti "$mods/jiti"
cp -a node_modules/get-east-asian-width "$mods/get-east-asian-width"
cp -a node_modules/marked "$mods/marked"
cp -a node_modules/esbuild "$mods/esbuild"

install -m0644 packages/chord/package.json "$mods/@earendil-works/chord/package.json"
install -m0644 packages/chord/README.md "$mods/@earendil-works/chord/README.md"
cp -a packages/chord/dist "$mods/@earendil-works/chord/dist"

install -m0644 packages/tui/package.json "$mods/@earendil-works/pi-tui/package.json"
cp -a packages/tui/dist "$mods/@earendil-works/pi-tui/dist"
cp -a packages/tui/native/linux/prebuilds "$mods/@earendil-works/pi-tui/native/linux/"

cat > "$mods/@esbuild/linux-%{esbuild_cpu}/package.json" <<EOF
{
  "name": "@esbuild/linux-%{esbuild_cpu}",
  "version": "0.28.2",
  "license": "MIT",
  "os": ["linux"],
  "cpu": ["%{esbuild_cpu}"]
}
EOF
install -m0755 esbuild-bin "$mods/@esbuild/linux-%{esbuild_cpu}/bin/esbuild"

find "$agent" "$mods/jiti" "$mods/esbuild" "$mods/marked" \
	"$mods/get-east-asian-width" "$mods/@earendil-works/chord" \
	-type f \( -name '*.wasm' -o -name '*.node' -o -name '*.so' -o -name '*.exe' \) -delete

ln -s %{_libdir}/pi/node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js \
	%{buildroot}%{_bindir}/pi

%files
%license LICENSE
%{_bindir}/pi
%{_libdir}/pi
