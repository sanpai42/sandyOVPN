#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="SandyVPN"
LAUNCH_SCRIPT="$APP_DIR/launch.sh"
DESKTOP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
DESKTOP_FILE="$DESKTOP_DIR/sandyvpn.desktop"
OPENVPN_APT_REPO_FILE="/etc/apt/sources.list.d/openvpn-packages.list"
OPENVPN_APT_KEY_FILE="/etc/apt/keyrings/openvpn.asc"

prompt_yes_no() {
  local prompt=$1
  while true; do
    read -r -p "$prompt [y/N] " reply
    case "$reply" in
      [yY]|[yY][eE][sS]) return 0 ;;
      [nN]|[nN][oO]|"") return 1 ;;
      *) echo "Please answer yes or no." ;;
    esac
  done
}

require_sudo() {
  if ! command -v sudo >/dev/null 2>&1; then
    echo "Error: sudo is required to install system packages." >&2
    exit 1
  fi
}

apt_distro_codename() {
  if command -v lsb_release >/dev/null 2>&1; then
    lsb_release -cs
    return 0
  fi

  if [[ -f /etc/os-release ]]; then
    # shellcheck disable=SC1091
    source /etc/os-release
    if [[ -n "${VERSION_CODENAME:-}" ]]; then
      echo "$VERSION_CODENAME"
      return 0
    fi
    if [[ -n "${UBUNTU_CODENAME:-}" ]]; then
      echo "$UBUNTU_CODENAME"
      return 0
    fi
  fi

  return 1
}

python3_minor_version() {
  python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'
}

apt_package_available() {
  local package=$1
  apt-cache show "$package" &>/dev/null
}

apt_install_packages() {
  local packages=("$@")
  local available=()
  local package

  for package in "${packages[@]}"; do
    if apt_package_available "$package"; then
      available+=("$package")
    fi
  done

  if ((${#available[@]} == 0)); then
    return 1
  fi

  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y "${available[@]}"
}

apt_install_one_of() {
  local packages=("$@")
  local package

  for package in "${packages[@]}"; do
    if apt_package_available "$package"; then
      sudo DEBIAN_FRONTEND=noninteractive apt-get install -y "$package"
      return 0
    fi
  done

  return 1
}

openvpn3_apt_codename_candidates() {
  local codename=$1
  local fallback

  printf '%s\n' "$codename"
  for fallback in noble jammy focal bookworm bullseye trixie; do
    if [[ "$fallback" != "$codename" ]]; then
      printf '%s\n' "$fallback"
    fi
  done
}

openvpn3_package_available() {
  apt_package_available openvpn3 || apt_package_available openvpn3-client
}

install_openvpn3_apt_packages() {
  apt_install_one_of openvpn3 openvpn3-client
}

configure_openvpn3_apt_repo() {
  local codename=$1

  require_sudo
  apt_install_packages curl ca-certificates lsb-release || {
    echo "Error: could not install curl or ca-certificates." >&2
    exit 1
  }
  apt_install_one_of apt-transport-https || true
  sudo mkdir -p /etc/apt/keyrings
  curl -fsSL https://packages.openvpn.net/packages-repo.gpg | sudo tee "$OPENVPN_APT_KEY_FILE" >/dev/null
  echo "deb [signed-by=${OPENVPN_APT_KEY_FILE}] https://packages.openvpn.net/openvpn3/debian ${codename} main" \
    | sudo tee "$OPENVPN_APT_REPO_FILE" >/dev/null
}

setup_openvpn3_apt_repo() {
  local codename
  codename=$(apt_distro_codename) || {
    echo "Error: could not detect this system's distribution codename." >&2
    echo "Install lsb-release or ensure /etc/os-release defines VERSION_CODENAME." >&2
    exit 1
  }

  local candidate
  while IFS= read -r candidate; do
    echo "==> Trying OpenVPN 3 apt repository (${candidate})"
    configure_openvpn3_apt_repo "$candidate"
    sudo apt-get update -qq
    if openvpn3_package_available; then
      echo "    Using repository codename: ${candidate}"
      return 0
    fi
  done < <(openvpn3_apt_codename_candidates "$codename")

  echo "Error: could not find OpenVPN 3 packages for this distribution." >&2
  echo "See: https://community.openvpn.net/openvpn/wiki/OpenVPN3Linux" >&2
  exit 1
}

install_openvpn3_apt() {
  require_sudo
  sudo apt-get update -qq

  if openvpn3_package_available; then
    echo "==> Installing OpenVPN 3 from apt"
    install_openvpn3_apt_packages
    return 0
  fi

  setup_openvpn3_apt_repo
  install_openvpn3_apt_packages
}

remove_openvpn2_apt() {
  if ! dpkg-query -s openvpn &>/dev/null 2>&1; then
    return 0
  fi

  echo "==> Removing classic OpenVPN 2 (openvpn)"
  if systemctl is-active --quiet openvpn.service 2>/dev/null; then
    sudo systemctl stop openvpn.service || true
  fi
  sudo DEBIAN_FRONTEND=noninteractive apt-get remove -y openvpn
}

install_openvpn3_dnf() {
  require_sudo

  if ! rpm -q openvpn-openvpn3-epel-repo &>/dev/null 2>&1; then
    echo "==> Adding official OpenVPN 3 dnf repository"
    sudo dnf install -y https://packages.openvpn.net/openvpn-openvpn3-epel-repo-1-1.noarch.rpm
  fi

  echo "==> Installing OpenVPN 3 (openvpn3-client)"
  sudo dnf install -y openvpn3-client
}

remove_openvpn2_dnf() {
  if rpm -q openvpn &>/dev/null 2>&1; then
    echo "==> Removing classic OpenVPN 2 (openvpn)"
    sudo dnf remove -y openvpn
  fi
}

install_openvpn3_system() {
  local remove_openvpn2=${1:-false}

  if command -v apt-get >/dev/null 2>&1; then
    if [[ "$remove_openvpn2" == true ]]; then
      remove_openvpn2_apt
    fi
    install_openvpn3_apt
  elif command -v dnf >/dev/null 2>&1; then
    if [[ "$remove_openvpn2" == true ]]; then
      remove_openvpn2_dnf
    fi
    install_openvpn3_dnf
  else
    echo "Error: could not install OpenVPN 3 automatically on this system." >&2
    echo "See: https://community.openvpn.net/openvpn/wiki/OpenVPN3Linux" >&2
    exit 1
  fi
}

ensure_openvpn3() {
  if command -v openvpn3 >/dev/null 2>&1; then
    return 0
  fi

  local has_openvpn2=false
  if command -v openvpn >/dev/null 2>&1; then
    has_openvpn2=true
  fi

  echo
  if [[ "$has_openvpn2" == true ]]; then
    echo "SandyVPN requires OpenVPN 3 (openvpn3), but the classic OpenVPN 2"
    echo "client (openvpn) was found on this system."
    echo
    echo "install.sh can remove openvpn and install openvpn3 for you."
    if ! prompt_yes_no "Proceed with replacing OpenVPN 2 with OpenVPN 3?"; then
      echo "Installation cancelled. Install OpenVPN 3 manually, then re-run this script." >&2
      exit 1
    fi
    install_openvpn3_system true
  else
    echo "OpenVPN 3 (openvpn3) was not found. SandyVPN requires it."
    if ! prompt_yes_no "Install OpenVPN 3 now?"; then
      echo "Installation cancelled. Install OpenVPN 3 manually, then re-run this script." >&2
      exit 1
    fi
    install_openvpn3_system false
  fi

  if ! command -v openvpn3 >/dev/null 2>&1; then
    echo "Error: openvpn3 is still not available after install." >&2
    exit 1
  fi
}

ensure_python_deps() {
  if command -v apt-get >/dev/null 2>&1; then
    ensure_python_deps_apt
  elif command -v dnf >/dev/null 2>&1; then
    ensure_python_deps_dnf
  else
    ensure_python_deps_generic
  fi
}

ensure_python_deps_generic() {
  if command -v python3 >/dev/null 2>&1 && python3 -c "import tkinter" 2>/dev/null; then
    return 0
  fi

  echo "Error: could not install Python dependencies automatically on this system." >&2
  echo "Install Python 3 with tkinter support, then re-run this script." >&2
  exit 1
}

ensure_python_deps_dnf() {
  local packages=()

  if ! command -v python3 >/dev/null 2>&1; then
    packages+=(python3)
  fi
  if ! python3 -c "import tkinter" 2>/dev/null; then
    packages+=(python3-tkinter)
  fi

  if ((${#packages[@]} == 0)); then
    return 0
  fi

  echo "==> Installing required system packages: ${packages[*]}"
  require_sudo
  sudo dnf install -y "${packages[@]}"
  verify_python_deps
}

ensure_python_deps_apt() {
  require_sudo
  sudo apt-get update -qq

  if ! command -v python3 >/dev/null 2>&1; then
    echo "==> Installing Python 3"
    apt_install_one_of python3 python3-minimal || {
      echo "Error: could not install python3." >&2
      exit 1
    }
  fi

  local python_version
  python_version=$(python3_minor_version)

  if ! python3 -c "import tkinter" 2>/dev/null; then
    echo "==> Installing Python tkinter support"
    apt_install_one_of python3-tk "python${python_version}-tk" || {
      echo "Error: could not install tkinter for Python ${python_version}." >&2
      echo "Try: sudo apt install python3-tk" >&2
      exit 1
    }
  fi

  verify_python_deps
}

ensure_python_venv_module() {
  if python3 -c "import venv" 2>/dev/null; then
    return 0
  fi

  if command -v apt-get >/dev/null 2>&1; then
    local python_version
    python_version=$(python3_minor_version)
    echo "==> Installing Python venv support"
    require_sudo
    sudo apt-get update -qq
    apt_install_one_of python3-venv "python${python_version}-venv" || {
      echo "Error: could not install the Python venv module." >&2
      echo "Try: sudo apt install python3-venv" >&2
      exit 1
    }
    return 0
  fi

  if command -v dnf >/dev/null 2>&1; then
    echo "==> Installing Python venv support"
    require_sudo
    sudo dnf install -y python3
    return 0
  fi

  echo "Error: Python venv module is not available." >&2
  exit 1
}

verify_python_deps() {
  if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 is still not available after install." >&2
    exit 1
  fi
  if ! python3 -c "import tkinter" 2>/dev/null; then
    echo "Error: python3-tk is still not available after install." >&2
    exit 1
  fi
}

echo "==> Installing $APP_NAME"
echo "    Location: $APP_DIR"
echo

chmod +x "$APP_DIR/launch.sh"
chmod +x "$APP_DIR/install.sh"

ensure_python_deps

ensure_openvpn3

ensure_python_venv_module

echo "==> Setting up Python virtual environment"
if [[ ! -d "$APP_DIR/.venv" ]]; then
  python3 -m venv "$APP_DIR/.venv"
fi

"$APP_DIR/.venv/bin/pip" install --upgrade pip || true

if ! "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"; then
  echo
  echo "Warning: could not install Python packages into .venv."
  if python3 -c "import cryptography, tkinter" 2>/dev/null; then
    echo "System Python already has the required packages."
    echo "launch.sh will use system Python instead."
  else
    echo "Error: missing Python dependencies." >&2
    echo "Try installing them with your system package manager, e.g.:" >&2
    echo "  sudo apt install python3 python3-tk python3-venv python3-pip" >&2
    exit 1
  fi
fi

echo
echo "==> Creating desktop launcher"
mkdir -p "$DESKTOP_DIR"

ICON_LINE="Icon=network-vpn"
if [[ -f "$APP_DIR/sandyvpn/assets/icon.png" ]]; then
  ICON_LINE="Icon=$APP_DIR/sandyvpn/assets/icon.png"
fi

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=$APP_NAME
Comment=OpenVPN 3 session launcher
Exec=$LAUNCH_SCRIPT
Path=$APP_DIR
$ICON_LINE
Terminal=false
Categories=Network;
StartupNotify=true
EOF

chmod +x "$DESKTOP_FILE"

if [[ -d "$HOME/Desktop" ]]; then
  ln -sf "$DESKTOP_FILE" "$HOME/Desktop/sandyvpn.desktop"
  echo "    Shortcut: $HOME/Desktop/sandyvpn.desktop"
fi

echo "    Menu entry: $DESKTOP_FILE"
echo
echo "Done. You can now:"
echo "  - Double-click launch.sh in this folder"
echo "  - Double-click SandyVPN on your Desktop"
echo "  - Search for SandyVPN in your application menu"
echo
echo "First time only: if your file manager asks, choose"
echo "\"Run\" or \"Allow executing file as program\" for launch.sh."
