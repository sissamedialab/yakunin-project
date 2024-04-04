# source this file to have bash compete yakunin command

_yakunin_completion () {
    # COMPREPLY # un array, ogni elemento è un possibile completamento
    # COMP_WORDS # un array, ogni elemento è una "parola" from command line
    # COMP_CWORD # indice della parola che sto completando
    local word=${COMP_WORDS[$COMP_CWORD]}

    # TODO: inelegant
    if [[ "${COMP_WORDS[@]}" =~ "compile" ]]
    then
        COMPREPLY=($(compgen -W "$(yakunin compile --help|sed -n 's/^  -\(.*\) .*/-\1/p'|cut -d' ' -f1|sed '/^-h,/d')" -- $word))
        return
    fi
    if [[ "${COMP_WORDS[@]}" =~ "mkpdf" ]]
    then
        COMPREPLY=($(compgen -W "$(yakunin mkpdf --help|sed -n 's/^  -\(.*\) .*/-\1/p'|cut -d' ' -f1|sed '/^-h,/d')" -- $word))
        return
    fi
    if [[ "${COMP_WORDS[@]}" =~ "watermark" ]]
    then
        COMPREPLY=($(compgen -W "$(yakunin watermark --help|sed -n 's/^  -\(.*\) .*/-\1/p'|cut -d' ' -f1|sed '/^-h,/d')" -- $word))
        return
    fi
    if [[ "${COMP_WORDS[@]}" =~ "pitstop_validate" ]]
    then
        COMPREPLY=($(compgen -W "$(yakunin pitstop_validate --help|sed -n 's/^  -\(.*\) .*/-\1/p'|cut -d' ' -f1|sed '/^-h,/d')" -- $word))
        return
    fi
    if [[ "${COMP_WORDS[@]}" =~ "topdfa" ]]
    then
        COMPREPLY=($(compgen -W "$(yakunin topdfa --help|sed -n 's/^  -\(.*\) .*/-\1/p'|cut -d' ' -f1|sed '/^-h,/d')" -- $word))
        return
    fi

    COMPREPLY=($(compgen -W "compile mkpdf watermark pitstop_validate topdfa" -- $word ))
}

complete -F _yakunin_completion yakunin
