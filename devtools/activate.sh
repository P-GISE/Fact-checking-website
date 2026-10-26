# Source this file: source devtools/activate.sh
fact_devtools_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.devtools"
export PATH="$fact_devtools_root/bin:$PATH"
export HF_HOME="$fact_devtools_root/huggingface"
export XDG_CACHE_HOME="$fact_devtools_root/cache"
export XDG_CONFIG_HOME="$fact_devtools_root/config"
export DATA_DIR="$fact_devtools_root/state/omniroute"
export HEADROOM_BEACON=off
export DO_NOT_TRACK=1
