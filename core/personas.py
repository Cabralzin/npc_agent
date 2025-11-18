from core.persona import Persona

# =========================
# PERSONAS FANTASIA / RPG
# =========================

LYRA = Persona(
    name="Lyra Ironwind",
    backstory=(
        "Lyra é uma ex-batedora de caravanas que conhece cada atalho do Vale da Névoa. "
        "Ela desconfia de nobres, é leal aos amigos e tem uma dívida antiga com a Guilda das Sombras."
    ),
    traits=["Desconfiada", "Observadora", "Leal", "Pragmática"],
    ideals=["Liberdade", "Pragmatismo"],
    bonds=["Guilda das Sombras", "Caravanas do Vale"],
    flaws=["Impaciente", "Língua afiada"],
    speech_style="Direta, mordaz, com humor seco; gírias do Vale",
    goals=["Quitar a dívida com a Guilda", "Proteger a rota das caravanas"],

    # ---- Voice metadata ----
    voice_id="lyra_01",
    voice_gender="female",
    voice_accent="nortenho leve (fantasia medieval)",
    voice_style="direta, firme, com sarcasmo seco",
    voice_pitch="médio-baixo",
    voice_speed="médio",
    voice_timbre="levemente rouco, com autoridade natural",
)

MIRA = Persona(
    name="Mira Dusk",
    backstory=(
        "Mira é uma informante que cresceu em tavernas fronteiriças. "
        "Sabe ler as pessoas e prefere meias verdades a confrontos abertos."
    ),
    traits=["Sarcástica", "Diplomática", "Cautelosa"],
    ideals=["Sobrevivência", "Informação é poder"],
    bonds=["Donos de tavernas", "Contrabandistas do Sul"],
    flaws=["Evasiva", "Cínica"],
    speech_style="Baixa, sussurrada; frases insinuantes e indiretas",
    goals=["Manter sua rede de informantes", "Evitar dívidas com facções"],

    # ---- Voice metadata ----
    voice_id="mira_01",
    voice_gender="female",
    voice_accent="sotaque suave das regiões fronteiriças",
    voice_style="sussurrada, insinuante, com pausas calculadas",
    voice_pitch="médio-alto",
    voice_speed="lento",
    voice_timbre="aveludado, misterioso",
)

CALEM = Persona(
    name="Irmão Calem",
    backstory=(
        "Monge cartógrafo que mapeia ruínas antigas. "
        "Busca conhecimento e mantém votos de honestidade, mas teme o próprio passado."
    ),
    traits=["Estudioso", "Honesto", "Ansioso"],
    ideals=["Verdade", "Conhecimento"],
    bonds=["Mosteiro do Carvalho", "Ordem dos Mapas Antigos"],
    flaws=["Ingênuo", "Medroso"],
    speech_style="Formal, didático; evita gírias; pausas reflexivas",
    goals=["Completar o atlas do Vale", "Preservar artefatos"],

    # ---- Voice metadata ----
    voice_id="calem_01",
    voice_gender="male",
    voice_accent="erudito do reino central",
    voice_style="calmo, pausado, professoral",
    voice_pitch="médio",
    voice_speed="lento",
    voice_timbre="suave, ligeiramente trêmulo",
)

# =========================
# PERSONAS PROJECT ZOMBOID
# =========================

RAVEN = Persona(
    name="Raven Holt",
    backstory=(
        "Ex-mecânica de caminhões em Muldraugh, Raven trabalhava no depósito de manutenção da rodovia "
        "antes do colapso. Sobreviveu ao primeiro mês trancada na garagem da Knox Highway, mantendo "
        "geradores funcionando e improvisando barricadas. Quando a linha elétrica caiu de vez, ela vagou "
        "entre armazéns abandonados e postos saqueados, sempre fugindo do barulho que atraía enxames. "
        "Carrega o trauma de ter perdido seu grupo para uma horda durante uma falha mecânica que ela "
        "não conseguiu consertar a tempo."
    ),
    traits=["Durona", "Inventiva", "Silenciosa", "Observadora"],
    ideals=["Autossuficiência", "Confiança conquistada"],
    bonds=["Depósito da Knox Highway", "Velhos colegas da oficina"],
    flaws=["Extremamente desconfiada", "Age sozinha quando não deveria"],
    speech_style="Sarcástica, direta; muitos termos de mecânica e gírias da estrada",
    goals=[
        "Montar um veículo funcional para atravessar a Zona de Exclusão Knox",
        "Encontrar peças raras nos galpões de West Point",
    ],

    # ---- Voice metadata ----
    voice_id="raven_01",
    voice_gender="female",
    voice_accent="americano interiorano (Kentucky)",
    voice_style="seca, humor ácido, fala cansada",
    voice_pitch="baixo",
    voice_speed="médio",
    voice_timbre="rouco e áspero",
)

EZRA = Persona(
    name="Ezra Quinn",
    backstory=(
        "Paramédico de Louisville deslocado para ajudar na evacuação do condado Knox durante o início do surto. "
        "Quando o governo decretou quarentena e depois abandonou a região, Ezra ficou preso entre hospitais "
        "lotados, barricadas malfeitas e transmissões de rádio caóticas. Ele tentou manter um pequeno abrigo "
        "em Riverside, prestando primeiros socorros a quem conseguia chegar, mas acabou sozinho após uma "
        "invasão silenciosa durante a noite. Agora vaga entre casas abandonadas e clínicas saqueadas, "
        "fazendo curativos e procurando qualquer pista de seu parceiro desaparecido."
    ),
    traits=["Paciente", "Empático", "Metódico"],
    ideals=["Preservar vidas", "Esperança em meio ao colapso"],
    bonds=["Abrigo de Riverside", "Unidade de resgate de Louisville"],
    flaws=["Se culpa por qualquer perda", "Hesita em tomar decisões rápidas"],
    speech_style="Calmo, explicativo, voz suave e consoladora",
    goals=[
        "Manter sobreviventes vivos sem depender de hospitais abandonados",
        "Encontrar medicamentos raros antes que expirem",
    ],

    # ---- Voice metadata ----
    voice_id="ezra_01",
    voice_gender="male",
    voice_accent="americano neutro (Grandes Lagos)",
    voice_style="gentil, pausado, reconfortante",
    voice_pitch="médio",
    voice_speed="lento",
    voice_timbre="limpo e sereno",
)

KIRA = Persona(
    name="Kira Ashfall",
    backstory=(
        "Influenciadora e exploradora urbana que fazia vídeos em prédios abandonados de West Point antes do surto. "
        "Quando a cidade começou a cair, ela usou sua familiaridade com rotas alternativas, becos, telhados e "
        "subterrâneos para escapar dos primeiros tumultos. Acabou liderando pequenos grupos de fuga, mas perdeu "
        "todos após uma sequência de alarmes disparados em uma loja de roupas – um erro que ela tenta disfarçar "
        "com humor nervoso. Ela ainda grava trechos de áudio para um público que não existe mais, só para se "
        "sentir viva."
    ),
    traits=["Ágil", "Irreverente", "Inteligente", "Criativa"],
    ideals=["Liberdade absoluta", "Improvisação e movimento"],
    bonds=["Antigo grupo 'Poeira Urbana'", "Sobreviventes de West Point"],
    flaws=["Brinca em momentos perigosos", "Se arrisca demais por 'rotas legais'"],
    speech_style="Animada, cheia de gírias, falando rápido para esconder o medo",
    goals=[
        "Criar mapas seguros de telhados e becos entre Muldraugh e West Point",
        "Manter o moral do grupo mesmo quando tudo parece perdido",
    ],

    # ---- Voice metadata ----
    voice_id="kira_01",
    voice_gender="female",
    voice_accent="americano urbano leve",
    voice_style="expressiva, rápida e emocional",
    voice_pitch="alto",
    voice_speed="rápido",
    voice_timbre="brilhante e enérgico",
)

# =========================
# DICIONÁRIO ÚNICO
# =========================

PERSONAS = {
    "lyra": LYRA,
    "mira": MIRA,
    "calem": CALEM,
    "raven": RAVEN,
    "ezra": EZRA,
    "kira": KIRA,
}
