# Treatment Definition — Romanian Administrative Reform

## File: ro_capital_status.csv

### Source
Manually compiled from:
- Romanian Parliament proposals for territorial-administrative reform, 2023–2025
- National Regional Development Strategy 2021–2027 (MDLPA)
- Eurostat NUTS 2021 classification

### Coverage
42 NUTS3 units: 41 județe (counties) + Municipiul București

### Column Definitions

| Column | Description |
|---|---|
| `nuts3_code` | Eurostat NUTS3 code (e.g., RO113 = Cluj) |
| `judet_name` | Romanian county name |
| `county_seat` | Main city (administrative seat) |
| `nuts2_code` | Parent NUTS2 region code |
| `siruta` | SIRUTA code (crosswalk with RO-Voting-Prediction data) |
| `current_status` | `county_capital` / `national_capital` / `special` |
| `proposed_regional_capital` | 1 = would become/stay regional capital under 2023-2025 proposals |
| `proposed_treatment` | 1 = would be demoted (lose county capital status) |
| `proposed_reform_year` | Hypothetical treatment year (2025; reform not yet enacted) |
| `notes` | Rationale and caveats |

### Treatment Logic

Under the most commonly cited 2023-2025 regional reform proposals:
- Romania's 41 counties would merge into **8 development regions**
- Each region would have **one regional capital** retaining/gaining administrative primacy
- **~33 county seats would lose capital status** (analogous to Poland's 1999 reform)

### Proposed Regional Capitals (8 units, `proposed_regional_capital=1`)

| Region | NUTS2 | Regional Capital | NUTS3 |
|---|---|---|---|
| Nord-Vest | RO11 | Cluj-Napoca (Cluj) | RO113 |
| Centru | RO12 | Brașov | RO122 |
| Nord-Est | RO21 | Iași | RO213 |
| Sud-Est | RO22 | Constanța | RO223 |
| Sud-Muntenia | RO31 | Ploiești (Prahova) | RO316 |
| București-Ilfov | RO32 | București | RO321 |
| Sud-Vest Oltenia | RO41 | Craiova (Dolj) | RO411 |
| Vest | RO42 | Timișoara (Timiș) | RO424 |

**Note:** Brașov vs. Sibiu for Centru regional capital is contested in the literature.
RO316 (Prahova/Ploiești) vs. RO311 (Argeș/Pitești) for Sud-Muntenia is also debated.
The choices above follow the most frequently cited proposals as of 2024.

### Important Caveat
The reform is **not yet enacted** (as of 2025). This project treats it as a **hypothetical treatment** for forecasting purposes. The analysis quantifies what would happen to demoted cities IF the reform proceeds, using Poland's 1999 reform as the causal baseline for reform costs.

### Crosswalk Note
`siruta` codes match the SIRUTA lookup table in `RO-Voting-Prediction/scripts/constants.py`.
