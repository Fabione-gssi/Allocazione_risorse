"""
Subset of ESCO (European Skills, Competences, Qualifications and Occupations)
taxonomy relevant to digital / IT / management roles.
"""

ESCO_SKILLS: dict[str, list[str]] = {
    "Sviluppo Software": [
        "Sviluppo applicazioni web",
        "Sviluppo applicazioni mobile",
        "Programmazione back-end",
        "Programmazione front-end",
        "Architettura software",
        "Sviluppo API REST",
        "Microservizi",
        "Test del software",
        "Revisione del codice",
        "Programmazione orientata agli oggetti",
        "Programmazione funzionale",
    ],
    "Linguaggi & Framework": [
        "Python",
        "Java",
        "JavaScript / TypeScript",
        "C / C++",
        "C#",
        "Go",
        "Rust",
        "Kotlin",
        "Swift",
        "PHP",
        "Ruby",
        "Scala",
        "React",
        "Angular",
        "Vue.js",
        "Node.js",
        "Django",
        "FastAPI",
        "Spring Boot",
        ".NET / ASP.NET",
    ],
    "Dati & AI": [
        "Analisi dei dati",
        "Data engineering",
        "Data warehousing",
        "Business intelligence",
        "Machine learning",
        "Deep learning",
        "Natural language processing",
        "Computer vision",
        "MLOps",
        "Statistica applicata",
        "SQL avanzato",
        "Big data (Spark, Hadoop)",
        "Visualizzazione dati",
    ],
    "Cloud & Infrastruttura": [
        "Amazon Web Services (AWS)",
        "Microsoft Azure",
        "Google Cloud Platform (GCP)",
        "Kubernetes",
        "Docker",
        "Terraform / Infrastructure as Code",
        "CI/CD (Jenkins, GitHub Actions)",
        "Site reliability engineering",
        "Networking",
        "Linux / Unix",
        "Virtualizzazione",
    ],
    "Sicurezza": [
        "Cybersecurity",
        "Penetration testing",
        "Gestione delle vulnerabilità",
        "Sicurezza delle applicazioni (OWASP)",
        "Gestione degli incidenti di sicurezza",
        "Crittografia",
        "Identity & Access Management",
        "Conformità normativa (GDPR, ISO 27001)",
    ],
    "Database": [
        "PostgreSQL",
        "MySQL / MariaDB",
        "Oracle Database",
        "Microsoft SQL Server",
        "MongoDB",
        "Redis",
        "Elasticsearch",
        "Cassandra",
        "Progettazione di database",
        "Ottimizzazione delle query",
    ],
    "UX / Design": [
        "User experience design",
        "User interface design",
        "Ricerca utente",
        "Prototipazione (Figma, Sketch)",
        "Accessibilità web",
        "Design system",
        "Usability testing",
    ],
    "Project & Product Management": [
        "Project management",
        "Agile / Scrum",
        "Kanban",
        "Product management",
        "Gestione del rischio",
        "Gestione del budget di progetto",
        "Pianificazione delle risorse",
        "Stakeholder management",
        "OKR / KPI",
        "PRINCE2",
        "PMP",
    ],
    "Analisi & Architettura": [
        "Analisi dei requisiti",
        "Business analysis",
        "Modellazione dei processi (BPMN)",
        "Architettura enterprise",
        "Architettura a microservizi",
        "Architettura cloud-native",
        "Analisi funzionale",
    ],
    "Soft Skills": [
        "Leadership tecnica",
        "Comunicazione tecnica",
        "Mentoring / Coaching",
        "Risoluzione dei problemi",
        "Lavoro in team",
        "Gestione del tempo",
        "Presentazione a stakeholder",
    ],
}

SENIORITY_LEVELS = ["Analyst", "SPE I", "SPE II", "EXP I", "EXP II", "DIR"]

PROJECT_STATUS_OPTIONS = [
    "In offerta",
    "In corso",
    "In pausa",
    "Completato",
    "Cancellato",
]

ALLOCATION_STATUS_OPTIONS = [
    "Confermata",
    "Proposta",
    "In revisione",
    "Terminata",
]


def all_skills_flat() -> list[str]:
    skills = []
    for category_skills in ESCO_SKILLS.values():
        skills.extend(category_skills)
    return sorted(set(skills))
