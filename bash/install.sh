#!/bin/bash
THIS_DIR="$(dirname "$(readlink -f "$0")")"
USER_BASHRC_D="$HOME/.bashrc.d"


function print_include_script()
{ 
    cat - <<EOF
BASHRC_D="$USER_BASHRC_D"
if [ -d "\$BASHRC_D" ]; then
  while IFS= read -r -d '' file; do
    source "\$file"
  done < <(find "\$BASHRC_D" -type f -name '*.sh' | sort -z)
fi
EOF
}


function add-bashrc-d-support()
{
    local bashrc="$HOME/.bashrc"
    local bashrc_d="$HOME/.bashrc.d"

    if [ ! -d "$USER_BASHRC_D" ]; then
        mkdir -p "$USER_BASHRC_D"
    fi

    local tag="kokoko-support-for-bashrc.d"
    local tag_start="# >>> $tag >>>"
    local tag_end="# <<< $tag <<<"
  
    if grep -q "$tag_start" "$bashrc"; then
        echo "script already exits in $bashrc" >&2
        return
    fi
    
    {
      echo -e "\n\n$tag_start"
      print_include_script
      echo "$tag_end"
    } >>"$bashrc"
}


function install-scripts()
{
    cp "$THIS_DIR/bashrc.d/"*.sh "$USER_BASHRC_D/"
}


case "$1" in
    install)
        add-bashrc-d-support
        install-scripts
        ;;
    *)
        echo "Usage: $0 install"
        ;;
esac