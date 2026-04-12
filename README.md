# Wieloskalowa agentowa symulacja rozprzestrzeniania się pandemii

Projekt zaliczeniowy z przedmiotu Modelowanie i Symulacja, AGH Informatyka.  
Celem jest stopniowa implementacja symulacji agentowej (ABM) pandemii wirusowej w środowisku miejskim.

## Stan projektu

| Etap | Opis | Status |
|------|------|--------|
| Etap 1 | Model SEIRD, architektura, prototyp MVP | Ukończony |
| Etap 2 | Graf POI, mechanika aerozoli/fomitów, dashboard Streamlit | W toku |
| Etap 3 | Eksperymenty badawcze, analiza wyników | Planowany |

## Szybki start

Wymagania: Python 3.10+, [uv](https://docs.astral.sh/uv/)

```bash
# Instalacja zależności
uv sync

# Uruchomienie symulacji MVP (100 kroków, N=500 agentów)
uv run python scripts/run_simulation.py

# Testy
uv run pytest
```

Wykres krzywych epidemicznych zapisywany jest do `data/output/epidemic_curve.png`.

## Model

Każdy agent przechodzi przez stany **SEIRD**:

```
S (Podatny) → E (Inkubacja) → I (Zakaźny) → R (Wyleczony)
                                           ↘ D (Zgon)
```

Parametry MVP (Etap 1):

| Parametr | Wartość |
|----------|---------|
| Liczba agentów | 500 |
| Siatka | 50 × 50 (torus) |
| Prawdopodobieństwo zakażenia na kontakt | 0.20 |
| Okres inkubacji | 4 dni |
| Czas zakaźności | 8 dni |
| Wskaźnik śmiertelności | 2% |

Emergentny współczynnik reprodukcji: **R₀ ≈ 2.6**

## Struktura projektu

```
pandemic-simulation/
├── pyproject.toml          # zależności i metadane pakietu
├── uv.lock                 # zamrożone wersje zależności
├── configs/                # pliki YAML z parametrami patogenu
├── data/
│   └── output/             # wykresy generowane przez symulację
├── src/simulation/
│   ├── agents.py           # HumanAgent, logika SEIRD
│   └── model.py            # EpidemicModel (rdzeń Mesa)
├── scripts/
│   └── run_simulation.py   # uruchamianie symulacji
├── tests/                  # testy pytest
└── reports/report1/        # raport z Etapu 1 (LaTeX)
```

## Stos technologiczny

- **Mesa** — framework do modelowania agentowego
- **NumPy / pandas** — obliczenia numeryczne i analiza danych
- **Matplotlib / Seaborn** — wizualizacja krzywych epidemicznych
- **Streamlit** — interaktywny dashboard (Etap 2)
- **pytest** — testy jednostkowe
- **uv** — zarządzanie zależnościami

## Autor

Dawid Mularczyk
