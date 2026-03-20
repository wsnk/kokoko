# Cross-terminal ssh-agent
export SSH_AUTH_SOCK="$HOME/.ssh/ssh_auth_sock"
function launch_ssh_agent { eval "$(ssh-agent -t 2h -a "$SSH_AUTH_SOCK")" ; }

if [ ! -S "$SSH_AUTH_SOCK" ]; then
    launch_ssh_agent
else
    ssh-add -l >/dev/null 2>&1
    if [[ $? == 2 ]] ; then
        # ssh-agent is not reachable
        rm -f "$SSH_AUTH_SOCK"
        launch_ssh_agent
    fi
fi