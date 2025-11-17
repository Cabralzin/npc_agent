from core.persona import Persona

LYRA = Persona(
    name="Lyra Ironwind",
    backstory=(
        "Lyra é uma ex‑batedora de caravanas que conhece cada atalho do Vale da Névoa. "
        "Ela desconfia de nobres, é leal aos amigos e tem uma dívida antiga com a Guilda das Sombras."
    ),
    traits=["Desconfiada", "Observadora", "Leal", "Pragmática"],
    ideals=["Liberdade", "Pragmatismo"],
    bonds=["Guilda das Sombras", "Caravanas do Vale"],
    flaws=["Impaciente", "Língua afiada"],
    speech_style="Direta, mordaz, com humor seco; gírias do Vale",
    goals=["Quitar a dívida com a Guilda", "Proteger a rota das caravanas"],
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
)

PERSONAS = {
    "lyra": LYRA,
    "mira": MIRA,
    "calem": CALEM,
}
