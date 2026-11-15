# Industry labelling guide

How to give a job its industry by hand. The hand labels are what the industry model learns from, so this guide is the definition of every industry: the model has no other rules.

**Status:** approved on 2026-11-13. 3,100 jobs were labelled with it by 2026-11-14, plus a test set of 200. The pipeline build that uses the labels is Phase 5, decision 15 ([`phases/phase-5-dashboards.md`](phases/phase-5-dashboards.md)).

## What a label is

- **One industry per job,** from the list below, or **Not classified**.
- **The industry is the kind of work the job is,** not the employer's sector or the product's subject:
  - a data analyst at a law firm is *Data Analytics & BI*, not Legal;
  - a product manager for a clinical lab system is *Product Management*, not Healthcare;
  - an account executive selling security software is *Sales & Business Development*, not Cybersecurity.
- **Read the title first.** Use the skills and the description only when the title leaves it open ("Consultant", "Specialist", "Engineer II").
- **"Engineer" decides nothing by itself.** A sales engineer sells, a quality engineer assures quality, a bridge engineer builds bridges.
- **A manager or lead of a field belongs to that field:** an Engineering Manager for infrastructure is *DevOps, Cloud & SRE*; a Head of Customer Success is *Customer Support & Success*.
- **Interns, working students and apprentices** get the field they work in.
- **A title naming several fields** ("Sales, Marketing & Projects") gets the first one, unless the description is clearly about another.
- **When two industries both fit,** use the tie-breaks at the end. If none applies, pick the one the title's main noun names, and mark the label as unsure.

## The industries

### Software

| Industry | What belongs | Typical titles |
|---|---|---|
| Backend | Server-side development. Also a title that names only a server-side language. | Backend Engineer, Java Developer, Python Engineer, Go Developer, .NET Developer, PL/SQL Developer |
| Frontend | Web interfaces in code. | Frontend Engineer, React Developer, Web Developer, UI Engineer, Design System Developer |
| Full-stack | The title says full-stack. | Full-Stack Engineer, Fullstack Entwickler |
| Mobile | Apps for phones. | iOS Developer, Android Engineer, React Native Engineer, Flutter Developer |
| Enterprise Applications | Building, configuring or running business platforms: SAP, Salesforce, ServiceNow, Workday, Oracle ERP, NetSuite, Dynamics, Guidewire, SharePoint. | SAP Consultant, Salesforce Administrator, ServiceNow Engineer, Business Systems Engineer, Oracle Retail Consultant |
| Solutions & Implementation | Technical work for customers after the sale: designing, integrating and rolling out the product for them. | Solutions Architect (delivery), Implementation Consultant, Forward Deployed Engineer, Technical Consultant, Integration Engineer |
| Software Engineering, general | Software work with no specialty in the title, and software specialties not listed above. Engineering leadership. | Software Engineer, Developer, Engineering Manager, CTO, Tech Lead, Software Architect, Game Developer |

### Data

| Industry | What belongs | Typical titles |
|---|---|---|
| Data Analytics & BI | Analysing data and reporting on it. | Data Analyst, BI Developer, Business Intelligence Analyst, Reporting Analyst, Insights Analyst, Statistician, Power BI Developer |
| Data Engineering | Building the pipelines, models and platforms data runs on. | Data Engineer, Analytics Engineer, Data Architect, Data Platform Engineer, ETL Developer |
| Machine Learning & AI | Building models and AI systems. | Data Scientist, Machine Learning Engineer, AI Engineer, Applied Scientist, Computer Vision Engineer, MLOps Engineer, AI Research Scientist |

A data title with no direction ("Head of Data", "Data Specialist") goes by its skills: pipeline tools mean Data Engineering, model libraries mean Machine Learning & AI, and BI tools, SQL or Excel mean Data Analytics & BI. With no hint, it's Data Analytics & BI, marked unsure.

### Infrastructure & Security

| Industry | What belongs | Typical titles |
|---|---|---|
| DevOps, Cloud & SRE | Running software in production: deployment, cloud platforms, reliability. | DevOps Engineer, Site Reliability Engineer, Platform Engineer, Cloud Engineer, Cloud Architect, Observability Engineer |
| IT Infrastructure & Administration | Running an organisation's own IT: networks, servers, databases, workplace systems. Also general IT roles. | Network Engineer, System Administrator, Database Administrator, IT Manager, Microsoft 365 Administrator, Informatiker |
| Cybersecurity | Protecting systems. | Security Engineer, SOC Analyst, Penetration Tester, IAM Engineer, CISO, Security Architect |

### Quality & Support

| Industry | What belongs | Typical titles |
|---|---|---|
| QA & Testing | Testing and quality assurance, of software or of anything else. | QA Engineer, Test Automation Engineer, SDET, Tester, Quality Engineer, Quality Manager, Quality Assurance Lead, Test Engineer |
| Technical Support | Solving users' technical problems. | Help Desk Technician, Service Desk Engineer, Support Engineer, Application Support Analyst, SAP Support Consultant |

### Hardware

| Industry | What belongs | Typical titles |
|---|---|---|
| Hardware & Embedded | Electronics, chips, and the software that runs on devices. | Hardware Engineer, Embedded Software Engineer, Firmware Engineer, FPGA Engineer, Robotics Engineer, RF Engineer |

### Design

| Industry | What belongs | Typical titles |
|---|---|---|
| UI & UX Design | Designing digital products and researching their users. | Product Designer, UX Designer, UI Designer, UX Researcher |
| Creative & Design | Visual and creative work outside product design. | Graphic Designer, Art Director, Motion Designer, Illustrator, Video Editor, Concept Artist, Interior Designer |

### Product & Projects

| Industry | What belongs | Typical titles |
|---|---|---|
| Product Management | Deciding what a product should be. | Product Manager, Product Owner, Head of Product |
| Project & Program Management | Getting projects delivered. Also business analysts who gather requirements. | Project Manager, Program Manager, Scrum Master, PMO Lead, Delivery Manager, Technical Program Manager, Business Analyst |

### Business

| Industry | What belongs | Typical titles |
|---|---|---|
| Sales & Business Development | Winning customers and partners, including the technical side of selling, and the sales team's own operations. | Account Executive, Sales Manager, SDR, BDR, Sales Engineer, Presales Consultant, Partnerships Manager, Territory Manager, Sales Operations Manager, Store Manager |
| Marketing | Reaching and persuading the market. | Marketing Manager, Growth Manager, SEO Manager, Brand Manager, Social Media Manager, Communications Manager, Creative Strategist |
| Customer Support & Success | Looking after customers after the sale. | Customer Success Manager, Customer Support Agent, Technical Account Manager, Onboarding Specialist, Reservations Agent |
| Finance & Accounting | Money: accounting, finance, tax, banking and insurance work. | Accountant, Financial Analyst, Controller, Tax Advisor, Payroll Specialist, Claims Handler, Credit Risk Manager |
| HR & Recruiting | People: hiring and looking after employees. | Recruiter, HR Business Partner, Talent Lead, People Operations Manager |
| Legal & Compliance | Law, regulation and compliance. | Lawyer, General Counsel, Paralegal, Compliance Officer, Data Protection Officer |
| Operations & Management | Running the business itself. | Operations Manager, COO, Chief of Staff, General Manager, Strategy Consultant, Workforce Planner |
| Content & Editorial | Writing, editing and language work. | Copywriter, Editor, Reporter, Technical Writer, Content Strategist, Translator, Linguist |
| Admin & Assistance | Office and assistant work. | Executive Assistant, Office Manager, Receptionist, Data Entry Clerk |

### Other fields

| Industry | What belongs | Typical titles |
|---|---|---|
| Engineering & Manufacturing | Engineering and trades outside software and electronics: mechanical, civil, construction, building services, production. | Mechanical Engineer, Bridge Engineer, Bauleiter, Elektroniker, Construction Project Manager, Fire Protection Engineer |
| Research & Science | Scientific research outside AI. | Research Scientist, Chemist, Materials Scientist, R&D Engineer |
| Healthcare & Medical | Care and clinical work, including clinical trials. | Nurse, Therapist, Audiologist, Clinical Research Associate, Medical Coder |
| Education & Training | Teaching, whatever the subject. | Teacher, Tutor, Instructor, Cloud Trainer, Instructional Designer |
| Logistics & Supply Chain | Moving and buying goods. | Logistics Manager, Freight Forwarder, Procurement Lead, Fulfilment Executive, Dispatcher |

### Not classified

For postings that aren't a job in any of these fields:
- **AI-training gigs:** paid per task or per hour to rate, annotate, record or review material for AI ("AI Trainer", "Data Rater", "Evaluator"). A contract or hourly research job is still Research & Science unless the work is training AI.
- **Talent pools and general applications,** which name no job.
- **Jobs in a field the list doesn't have,** such as fundraising or ministry.

## Tie-breaks

| The job | Industry | Why |
|---|---|---|
| Sales Engineer, Presales Consultant, a Solutions Engineer or Solutions Consultant who demonstrates the product to prospects | Sales & Business Development | The work is winning the deal |
| Solutions Architect or consultant who builds for existing customers | Solutions & Implementation | The work is delivery |
| Technical Account Manager | Customer Support & Success | The work is the customer relationship |
| Account Manager, with nothing else to go on | Sales & Business Development | Most carry a sales target |
| Revenue Operations, Sales Operations | Sales & Business Development | Part of the sales team |
| A quality role of any kind ("Quality Engineer", "Data QA Analyst") | QA & Testing | Quality assurance, whatever its object |
| Software engineer on a data team, building pipelines or a data platform | Data Engineering | The work, not the title's first word |
| Software or backend engineer building AI or ML systems ("Software Engineer, Machine Learning") | Machine Learning & AI | AI is the subject of the job |
| Developer who only uses AI tools to write code ("AI-native Fullstack Developer") | The software industry the title names | AI is the tool, not the subject |
| Research Scientist in AI or ML | Machine Learning & AI | |
| Software engineer on a security product | The software industry the title names | Only security roles are Cybersecurity |
| Embedded engineer working on security | Hardware & Embedded | |
| DevOps Engineer whose title also names a language | DevOps, Cloud & SRE | |
| Database Administrator, Database Engineer | IT Infrastructure & Administration | |
| Tech Lead or Team Lead naming a stack ("Tech Lead, Java") | The industry of that stack | |
| Engineering Manager, VP Engineering, CTO, with no team named | Software Engineering, general | |
| Business Analyst working on reports and dashboards | Data Analytics & BI | |
| Business Analyst gathering requirements for a system | Project & Program Management | |
| Functional analyst or consultant for a named platform ("Business Analyst – Oracle CPQ") | Enterprise Applications | |
| Support for a named platform ("SAP Support Consultant") | Technical Support | The work is support |
| Trainer or teacher of a technical subject | Education & Training | |
| Construction or site project manager | Engineering & Manufacturing | The work needs that field's engineering |
| Technical Program Manager, IT Project Manager | Project & Program Management | |
| Product Manager for any subject | Product Management | |
| Clinical research and clinical trial roles | Healthcare & Medical | |
| User researcher | UI & UX Design | |
| Market or customer-insight researcher | Marketing | |
| Graphic or brand designer in a marketing team | Creative & Design | |
| Creative or brand strategist, campaign roles | Marketing | |
| Copywriter | Content & Editorial | |
| Insurance or bank advisor to customers | Finance & Accounting | |
| General "IT" role with no specialty | IT Infrastructure & Administration | |
| Strategy consultant, business consultant | Operations & Management | |
| Strategy analyst | Operations & Management, or Data Analytics & BI when the skills are BI tools | |
| A general software title ("Senior Developer", "Principal Software Engineer") whose skills show a specialty | Software Engineering, general | The title decides. If skills decided, a skill's industries would partly follow from the skill itself |
| "Software Engineer (Cloud)", "Cloud Software Engineer" | Software Engineering, general | Only "Cloud Infrastructure" or "Platform" in the title makes it DevOps, Cloud & SRE |
| Solutions Engineer, with nothing else to go on | Sales & Business Development | Most are pre-sales |
| Solutions Architect or Integration Architect, with nothing else to go on | Solutions & Implementation | |
| Forward Deployed AI Engineer | Solutions & Implementation | The work is delivery for customers |
| Data Scientist working on product or marketing analytics | Machine Learning & AI | Data scientists stay together |
| Data governance roles, knowledge-graph engineers, ontologists | Data Engineering | |
| Business Systems Analyst | Enterprise Applications | |
| Reliability, safety (HSE) and field service engineers | Engineering & Manufacturing | |
| Developer Advocate | Marketing | |
| Field interviewers, mystery shoppers, postings that list several unrelated roles | Not classified | |
| "Expert – Remote", "STEM Expert (PhD), Remote – Contract" and similar postings that name a subject but no job | Not classified | They are almost always AI-training gigs |
| "Research Scientist – Remote" in the same style, naming a science | Research & Science | The title names a research job |
| Trade career coaches ("Electrician Career Coach"), training program managers, training coordinators | Education & Training | The work is teaching or organising it |
| Go-to-market roles ("Head of Go-to-Market", "GTM Engineer") | Sales & Business Development | Unless the title or skills are clearly marketing |
| Risk roles outside credit risk: enterprise risk, operational risk, audit coordination | Legal & Compliance | Credit and portfolio risk stay in Finance & Accounting |
| Account and client directors at agencies | Sales & Business Development | Like account managers |
| Developers, architects and consultants for a business platform the list doesn't name (Appian, Avaloq, Adobe Experience Platform, HubSpot, MuleSoft, Atlassian, Genesys, Veeva, Yardi) | Enterprise Applications | The list of platforms is open |
| "AI Solutions Engineer", and solutions architects with no hint of sales or delivery | Solutions & Implementation | |
| Value engineers, and field engineering managers at software vendors | Sales & Business Development | Both are pre-sales |
| Event managers | Marketing | |
| Content creators, SEO content leads | Marketing | Writers and editors stay in Content & Editorial |
| Building and landscape architects | Engineering & Manufacturing | With construction |
| Drivers and operators of construction machines | Engineering & Manufacturing | |
| Beauty, shop-floor and other jobs in fields the list lacks | Not classified | |
| Internal AI and automation roles ("AI Transformation Strategist", "AI Implementation Intern", "AI Workflow Engineer") | Operations & Management for strategists, owners and interns; Machine Learning & AI or Software Engineering, general for engineers, by what they build | The title's noun decides |
| Retail product and category roles ("Responsable Produit – Joaillerie", "Category Manager", "Marketplace Manager", "E-Commerce Manager") | Sales & Business Development | They manage what a shop sells, not a software product |
| "Infrastructure Engineer" whose skills are deployment tools (Ansible, CI/CD, Kubernetes, Terraform) | DevOps, Cloud & SRE | Otherwise IT Infrastructure & Administration |
| A general software title followed by a platform or company name ("Software Development Engineer III, MuleSoft") | Software Engineering, general | The name is the team or employer; "MuleSoft Developer" stays Enterprise Applications |
| Senior business titles with no field ("Vice President, International", "Vice President of Retail", "Country Manager") | Operations & Management | |
| Engineering manager of a software team working on a security product | Software Engineering, general | Like its engineers |
| Operational research scientists | Machine Learning & AI | |
| Debt collection roles | Finance & Accounting | |

## How the labelling runs

1. **The test set:** 200 randomly drawn jobs, judged once and never used for training. Every version of the model is scored on them.
2. **Batches of about 500 jobs** for training, picked where the model is least sure and in industries with few examples.
3. **After each batch,** the model is retrained and scored on the test set. Labelling stops when the score stops improving.
4. **Review:** you check a sample of each batch and every label marked unsure. A correction that states a general rule goes into this guide, and earlier labels it affects are redone.
5. **Storage:** a label is a job key, an industry, a batch number and a date, in a Databricks table. No title or description is stored with it, and none goes into this repository.
