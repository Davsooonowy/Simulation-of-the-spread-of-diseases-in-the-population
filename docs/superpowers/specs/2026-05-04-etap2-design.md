# Etap 2 — Implementacja i wstępna weryfikacja

**Data:** 2026-05-04  
**Projekt:** Wieloskalowa agentowa symulacja rozprzestrzeniania się pandemii wirusowej  
**Kamień milowy:** Etap 2 z raportu `reports/report1/report1.tex`

---

## Cel

Przebudowa modelu MVP z siatki MultiGrid na graf POI (NetworkX), implementacja pełnych atrybutów agentów, mechaniki maseczek i dystansu społecznego, interaktywnego dashboardu Streamlit oraz testów jednostkowych z analizą wrażliwości.

Zasada: każdy krok symulacji = 1 dzień. W każdym dniu agent odwiedza sekwencję POI; transmisja liczy się oddzielnie w każdym węźle.

---

## Struktura plików

```
src/simulation/
  agents.py          ← rozbudowany HumanAgent
  model.py           ← EpidemicModel na POI graph
  space.py           ← nowy: POI graph (NetworkX)
  transmission.py    ← nowy: formuły transmisji
  __init__.py

configs/
  pathogen_base.yaml
  scenario_lockdown.yaml

tests/
  __init__.py
  test_compartments.py
  test_poi.py

scripts/
  run_simulation.py  ← zaktualizowany
  dashboard.py       ← Streamlit
  sensitivity_analysis.py
```

---

## Agenci

### Nowe atrybuty `HumanAgent`

| Atrybut | Typ | Opis |
|---|---|---|
| `age` | int | 0–100 |
| `age_group` | str | `child` (<18), `adult` (18–65), `senior` (65+) |
| `household_id` | int | ID węzła domowego |
| `workplace_id` | int\|None | ID węzła pracy/szkoły; None dla seniorów |
| `wears_mask` | bool | Redukuje emisję i podatność |
| `social_distancing` | bool | Pomija sklep, mnożnik p_base ×0.8 |
| `viral_load` | float [0–1] | Narasta liniowo w E (0→1), maleje liniowo w I (1→0) |
| `immunity` | float [0–1] | Bazowa odporność; modyfikowana wiekiem i szczepieniem |
| `vaccinated` | bool | −50% podatności, −80% p_death |
| `hygiene_score` | float [0–1] | Rezerwa na fomity (Etap 3) |
| `contact_rate` | float | Multiplier interakcji (superspreader w Etapie 3) |

### Harmonogram dzienny (Opcja A — step = dzień)

W każdym `step()` agent odwiedza POI w kolejności:
1. **Household** — zawsze
2. **Workplace/School** — dorośli (office) i dzieci (school); pomijane tylko jeśli lockdown
3. **Shop** — z prawdopodobieństwem 0.3; pomijane przy `social_distancing=True`

Transmisja obliczana oddzielnie dla każdego odwiedzonego węzła.

---

## Graf POI (`space.py`)

Implementacja: `networkx.Graph` gdzie węzły to obiekty `POINode`.

### Typy węzłów i p_base

| Typ (`POIType`) | `p_base` | Liczba węzłów |
|---|---|---|
| `HOUSEHOLD` | 0.35 | `n_agents // 4` |
| `SCHOOL` | 0.30 | 2 |
| `OFFICE` | 0.20 | 3 |
| `SHOP` | 0.10 | 2 |
| `PARK` | 0.03 | 1 |
| `HEALTHCARE` | 0.15 | 1 |

### POINode atrybuty
- `node_id: int`
- `poi_type: POIType`
- `p_base: float`
- `agents: list[HumanAgent]` — agenci aktualnie w węźle

---

## Mechanika transmisji (`transmission.py`)

### Formuła bazowa (eq. poi-inf z raportu)

```
P_inf = 1 - (1 - p_eff)^W
```

gdzie `W = Σ viral_load_i` dla wszystkich zakaźnych agentów `i` w węźle.

### Modyfikator maseczek (eq. mask z raportu, η_M = 0.5)

```
p_eff = p_base × (1 − η_M)²   # obie strony w maseczce
p_eff = p_base × (1 − η_M)    # jedna strona w maseczce
p_eff = p_base                  # brak maseczek
```

### Modyfikator social distancing

```
p_eff × 0.8   (jeśli susceptible agent ma social_distancing=True)
```

### Modyfikator odporności

```
P_final = P_inf × (1 − immunity)
```

### Viral load

- Stan E, dzień `d` z `incubation_period` dni: `viral_load = d / incubation_period`
- Stan I, dzień `d` z `infectious_period` dni: `viral_load = 1 − d / infectious_period`
- Pozostałe stany: `viral_load = 0`

---

## Dashboard Streamlit (`scripts/dashboard.py`)

### Sidebar (parametry)

- `n_agents`: slider 100–2000 (default 500)
- `initial_infected_frac`: slider 1%–20% (default 5%)
- `mask_coverage`: slider 0–100% (default 0%)
- `social_distancing_coverage`: slider 0–100% (default 0%)
- `vaccination_coverage`: slider 0–100% (default 0%)
- `steps`: slider 50–200 (default 100)

### Główna sekcja (po kliknięciu "▶ Uruchom symulację")

1. Wykres krzywych SEIRD (Matplotlib)
2. Tabela końcowych statystyk: peak I, final R, total D, attack rate
3. Bar chart — rozkład agentów po typach POI na koniec symulacji

---

## Analiza wrażliwości (`scripts/sensitivity_analysis.py`)

Siatka 5×5:
- `p_base_multiplier` ∈ {0.5, 0.75, 1.0, 1.25, 1.5}
- `eta_M` ∈ {0.3, 0.4, 0.5, 0.6, 0.7}

Dla każdej kombinacji: 3 niezależne uruchomienia → uśrednione `peak_I` i `attack_rate`.

Wynik: heatmapa 5×5 zapisana do `data/output/sensitivity_heatmap.png`.

---

## Testy (`tests/`)

### `test_compartments.py`

- S→E przy kontakcie z I (p_inf=1.0, bez maseczek, immunity=0)
- E→I po `incubation_period` krokach
- I→R przy `p_death=0.0`
- I→D przy `p_death=1.0`
- Martwy agent (D) nie zmienia stanu po kroku

### `test_poi.py`

- P_inf rośnie z liczbą zakaźnych agentów w węźle
- Maseczka (obie strony) redukuje p_eff o (1−η_M)²
- Social distancing stosuje mnożnik 0.8
- Immunity=1.0 gwarantuje P_final=0
- Agent z `social_distancing=True` nie odwiedza węzłów SHOP

---

## Konfiguracja YAML

### `configs/pathogen_base.yaml`
Parametry patogenu, p_base per typ POI, η_M, p_death, okresy inkubacji i zakaźności.

### `configs/scenario_lockdown.yaml`
Nadpisuje p_base dla OFFICE i SHOP wartością 0.0 (zamknięte).

---

## Zależności do dodania

- `networkx>=3.0` — graf POI
- `streamlit>=1.32` — dashboard
- `pyyaml>=6.0` — konfiguracja YAML

Do `pyproject.toml` i instalacji przez `uv`.
