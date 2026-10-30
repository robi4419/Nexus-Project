"""Tell whether a job title is clearly Tech, for Himalayas jobs that come without any parent category.

On 2026-10-30, a day of the Himalayas feed had 27% of its jobs without a parent category, and sorting their titles found
about 1 in 5 clearly Tech (Phase 4, decision 8). Half of those are enterprise-systems roles (SAP, Workday, Oracle,
Epic); the rest are software, security, IT support, data, product, design, hardware and research jobs.

`tech_category` answers with one of Himalayas' own Tech parent categories, so landing keeps the job like any other
Tech job, and silver maps the same answer to an industry through `industries.csv`. Left out on purpose:
- AI-training gigs, whose titles name a field but whose work is rating AI output ("Chemist - Fully Remote | Upto
  $70/hr", "Audio Engineer - AI Trainer");
- non-Tech jobs with a Tech word in the title ("Patent Attorney, Electrical Engineering", "Instructional Designer");
- Tech-adjacent roles the title alone can't settle (AI strategy, clinical data management, IT audit, GTM engineers).
"""

import re

# Himalayas' parent categories that count as Tech (Phase 2b, decision 5).
TECH_CATEGORIES = frozenset(
    {"Developer", "Data Science", "Product", "Design", "Hardware Engineer", "Research & Development"}
)

# Checked first: a title with any of these isn't clearly Tech, whatever else it says.
_LEFT_OUT = re.compile(
    "|".join(
        [
            # AI-training gigs: "Fully Remote | Upto $40/hr", AI trainers and tutors, annotation, rating, evaluation
            r"\bupto\b|up to \$|\bai (?:trainer|tutor)|\bai safety (?:expert|specialist|red team)|\bai red team"
            r"|\bai (?:training|evaluation)\b(?!\s+(?:engineer|scientist|researcher|infrastructure|platform))"
            r"|annotat|\blabel(?:l)?ing\b|training data|evaluator|\brater\b|code evaluation"
            r"|(?:teaching|industry|engineering|programming) experts?",
            # non-Tech jobs: legal, teaching, language, sales, and the design of physical things
            r"patent|attorney|counsel|lawyer|paralegal|\blegal\b"
            r"|faculty|professor|lecturer|instructor|teacher|\btutor|grader|facilitat|adjunct"
            r"|interpreter|interpreting|(?<!machine )translat(?:ors?|ions?)\b|linguist|voice (?:actor|talent|over)"
            r"|(?<!large )(?<!natural )(?<!programming )\blanguages?\b(?!\s+models?)"
            r"|business develop|(?<!pre-)(?<!pre )\bsales\b(?!\s*(?:engineer|force))"
            r"|account (?:executive|manager|director|representative)|r&d tax|tax credit|\bgas\b|autocad|civil 3d"
            r"|substation|\b(?:civil|structural|mechanical|electrical|mep|piping|hvac|plumbing|landscape|interior"
            r"|fashion|kitchen|floral|lighting|jewel(?:le)?ry|textile|apparel|footwear|packaging|instructional|learning"
            r"|learning experience|curriculum|course|exhibit(?:ion)?|event|costume|store|set|site|control systems?"
            r"|workshop) design",
            # Tech-adjacent, but the title alone can't settle it
            r"\bai\b.{0,25}(?:strateg|transformation|enablement|adoption)"
            r"|(?:strateg|transformation|enablement|adoption).{0,25}\bai\b|\bgtm\b|go-to-market"
            r"|technical (?:account|customer success)|clinical (?:trials? )?data (?:manag|special)|clinical scientist"
            r"|technology (?:strategy|leader|project)|\bsox\b|(?-i:\bIT\b) (?:(?:internal )?audit|finance|vendor)"
            r"|validation engineer|field service",
        ]
    ),
    re.IGNORECASE,
)

# "Developer" outside software: business and product developers, property developers, curriculum developers, ...
_NOT_SOFTWARE = (
    "business", "product", "process", "formulation", "recipe", "property", "estate", "land", "material", "supplier",
    "curriculum", "course", "content", "learning", "talent", "leadership", "fund", "community", "market", "partner",
    "channel", "donor", "resource", "economic", "workforce", "organizational", "organisational",
)
_DEVELOPER = "".join(f"(?<!{word} )" for word in _NOT_SOFTWARE) + "developer"

# Enterprise systems count with a systems role anywhere in the title ("SAP FICO Consultant", "Epic Ambulatory
# Analyst"); the platform alone isn't enough ("Payroll Specialist with SAP experience").
_PLATFORMS = (
    r"sap|workday|oracle|salesforce|epic|ehr|emr|netsuite|dynamics 365|business central|coupa|appian|mulesoft|genexus"
    r"|sharepoint|ifs|yardi|lims|plm|creatio|zoho|adobe experience|aep|power (?:platform|apps|automate)"
)
_SYSTEMS_ROLES = (
    r"consultant|consulting|berater(?:in)?|developer|programmer|architect|engineer|administrator|admin|analyst"
    r"|functional|technical|techno|integrations?|implementation|support|configuration|expert|experte"
)
_PLATFORM_AND_ROLE = rf"^(?=.*\b(?:{_PLATFORMS})\b)(?=.*\b(?:{_SYSTEMS_ROLES})\b)"

# Checked in this order and the first match wins, so "Data Platform Architect" is Data Science and "Product Designer"
# is Design. Developer comes last because its words are the broadest.
_RULES = [
    (category, re.compile(words, re.IGNORECASE))
    for category, words in [
        (
            "Design",
            r"designer|\bux\b|\bui\b|user experience|user interface|user research|interaction design|product design"
            r"|visual design|web design|graphics? (?:design|artist)|motion (?:graphics|design)|illustrat|animat"
            r"|\b3d\b.{0,15}(?:artist|model|generalist)|(?:environment|concept) artist|art director|video editor"
            r"|game (?:artist|designer)|figma",
        ),
        (
            "Data Science",
            r"\bdata (?:scien|engineer|analy|architect|platform|infrastructure|warehouse|model|governance|quality"
            r"|product|lead|manager|ops|strateg|sme|storage|team|visuali[sz]|integration|migration)|dataops"
            r"|\b(?:data|ai) (?:and|&) (?:ai|data|modeling)\b|chief data|\bdata$"
            r"|machine learning|\bml\b|mlops|deep learning|\bnlp\b|computer vision|\bllms?\b|large language model"
            r"|\bgen ?ai\b|\bai\b.{0,30}(?:engineer|scientist|researcher|architect|developer|platform)|agentic"
            r"|artificial intelligence|analytics|business intelligence"
            r"|\bbi (?:developer|analyst|engineer|architect|consultant|specialist|lead|manager)|power bi|tableau"
            r"|\blooker\b|statistic|databricks|snowflake|\betl\b|multimodal"
            r"|\b(?:analista|analyste|cientista|científic[oa]|engenheir[oa]|ingenier[oa]|ingénieur)\b.{0,20}"
            r"\b(?:dados|datos|données)\b",
        ),
        (
            "Product",
            r"product (?:manager|management|owner|lead|director|head|strateg|operations|analyst|ops|delivery)"
            r"|\b(?:vp|vice president|svp|evp|director|chief|head)\W{1,3}(?:of\s)?product\b"
            r"(?!\s+(?:marketing|quality|safety|compliance|supply|development|education|support))"
            # project and program managers only with a Tech word nearby ("Technical Program Manager")
            r"|\b(?:technical|security|(?-i:IT)|software|data|cloud|ai|engineering|solutions?)\b.{0,25}"
            r"(?:project|program|programme|delivery) manager|scrum master|agile coach",
        ),
        (
            "Hardware Engineer",
            r"\bhardware\b(?!\s+store)|electrical engineer|electronics? engineer|electronic design|power electronics"
            r"|\bfpga|\basic\b|\bvlsi\b|analog (?:layout|design|circuit|mixed)|layout engineer|\brf engineer|\bpcb\b"
            r"|semiconductor|silicon (?:engineer|design|validation|verification)|(?:pre|post)-silicon|chip design"
            r"|robotics|mechatronic|firmware|embedded|field application|controls and automation",
        ),
        (
            "Research & Development",
            r"research (?:scientist|engineer)|(?<!data )scientist|chemist|physicist|\bphysics\b|mathematician"
            r"|computational|bioinformatic|biochem|molecular biolog|materials? science|\br&d\b"
            r"|research (?:and|&) development",
        ),
        (
            "Developer",
            # software, and engineering leadership
            r"software|programmer|computer science|devops|devsecops|\bsre\b|reliability engineer|back[- ]?end"
            r"|front[- ]?end|full[- ]?stack|\bcuda\b|kernel|\bedi\b|endpoint|webmaster|" + _DEVELOPER
            + r"|\b(?:web|mobile|ios|android|cloud|platform|infrastructure|systems?|network|security|application"
            r"|integrations?|qa|test|automation|database|game(?:play)?|graphics|rendering|forward[- ]deployed"
            r"|solutions?|implementation|api|blockchain|java|python|react|node(?:\.js)?|php|ruby|golang|rust|enterprise"
            r"|technical|identity)\s+(?:engineer|engineering|developer|architect)"
            r"|engineering (?:lead|manager|director|head|leader)|\b(?:director|head|vp|vice president) of "
            r"(?:engineering|technology)|\bvp\W{1,3}engineering|\bcto\b|chief technology|founding engineer"
            r"|member of (?:the )?technical staff|staff engineer|technical (?:lead|writer|consultant|solution|deployment)"
            r"|tech lead|sales engineer|implementation (?:consultant|specialist)|creative technolog"
            r"|infrastructure\W+(?:technology|and platform)"
            # security
            r"|cyber|infosec|information security|penetration test|security (?:operations|analyst|consultant"
            r"|specialist)|application security|appsec|secops|\bsoc\b|vulnerabilit|threat|digital forensics|\bdfir\b"
            r"|incident response|\biam\b|\biga\b|sailpoint|identity (?:and|&) access"
            # IT support and administration
            r"|(?-i:\bIT\b)|help ?desk|service desk|desktop support|tech(?:nical)? support|production support"
            r"|application support|applications? analyst|(?:support|success) engineer|\bnoc\b|finops|sysadmin|\bdba\b"
            r"|\b(?:system|network|database|sharepoint|platform|cloud|basis|oci|microsoft|azure|aws|linux|windows|jira"
            r"|technical|access|m365|active directory)\b.{0,12}administrator"
            # enterprise systems
            r"|business systems|systems analyst|financial systems|enterprise applications|techno.?functional"
            r"|system integration|client integrations|\bhr (?:technology|systems)|\bhris\b|\berp\b|servicenow"
            r"|crm (?:platform|developer|admin|administrator|architect|consultant|engineer)|abap|fiori|fscm|\bewm\b"
            r"|s/?4\s?hana|successfactors|" + _PLATFORM_AND_ROLE
            # other languages
            + r"|desarrollador|desenvolvedor|développeu|programador|programmeur|informatiker"
            r"|(?:anwendungs|web|sap|java|python|backend|frontend)-?entwickler",
        ),
    ]
]


def tech_category(title: str | None) -> str | None:
    """The Tech parent category a job title clearly belongs to, or None when it isn't clearly Tech: no Tech word, an
    AI-training gig, a non-Tech job with a Tech word, or a Tech-adjacent role the title alone can't settle."""
    title = " ".join((title or "").split())
    if _LEFT_OUT.search(title):
        return None
    return next((category for category, pattern in _RULES if pattern.search(title)), None)
