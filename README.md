# Data Quality Multi-Agent System

**Team members:** Nurkhanym Ziyabek (810081), Emanuele Aicardi (814361), Kamila Dochshanova (809891)  
**Captain:** Nurkhanym Ziyabek — Student ID: 810081

---

## Section 1 — Introduction

NoiPA is the digital platform of the Italian Ministry of Economy and Finance that manages salaries, timesheets, and tax/social security obligations for employees of the Italian Public Administration. It periodically receives datasets from heterogeneous sources containing demographic, economic, and tax data. Currently, validation of these datasets is manual or nonexistent, making the process error-prone and time-consuming.

This project builds a **multi-agent system** that receives a raw CSV dataset, automatically detects quality issues, fixes them, and produces a structured quality report including anomalies, correction suggestions, and a final reliability score. The system was tested on two synthetic datasets and two real NoiPA datasets (`spesa.csv` and `attivazioniCessazioni.csv`).

---

## Section 2 — Methods

The system is composed of five specialized agents, each responsible for a specific type of data quality check, orchestrated by a central `run_pipeline` function.

**1. Schema Agent** — validates column naming conventions (special characters, leading digits, whitespace) and detects mixed data types within columns. The schema score starts at 100 and subtracts 5 points per issue found.

**2. Completeness Agent** — counts missing values and placeholder strings (e.g. "N/A", "-", "unknown") per column, computes a completeness percentage per column and overall, and flags sparse columns where more than 50% of values are missing. The completeness score equals the overall completeness percentage directly.

**3. Consistency Agent** — detects exact duplicate rows, flags inconsistent string casing within columns, and checks cross-column logical rules (e.g. the `Rata` column must follow the YYYYMM format). The consistency score starts at 100 and subtracts 5 points per issue.

**4. Anomaly Agent** — applies the Z-score method to detect numerical outliers (values more than 3 standard deviations from the mean) and flags rare categorical values appearing less than 1% of the time. The anomaly score starts at 100 and subtracts 2 points per numerical outlier and 5 points per categorical anomaly.

**5. Remediation Agent** — aggregates findings from all agents, generates concrete actionable suggestions for each issue, and computes a final weighted **reliability score**:

$$\text{Reliability} = 0.2 \times \text{Schema} + 0.3 \times \text{Completeness} + 0.3 \times \text{Consistency} + 0.2 \times \text{Anomaly}$$

If any score is missing, a default value of 50 is used. The agent also writes a plain language summary of the dataset quality.

A `fix_dataset` function automatically applies corrections: removing duplicates, dropping sparse columns, converting numeric-like strings, imputing missing values (median for numeric columns, mode for categorical), standardizing string casing to title case, and capping outliers at ±3 standard deviations.

An optional LLM integration (local Ollama with `llama3`, or Groq API with `mixtral-8x7b-32768`) can enhance the natural language output of the Remediation Agent. If neither is available, the system automatically falls back to rule-based text generation — the pipeline always runs completely without any LLM.

The pipeline follows a **Supervisor Architecture**: the `run_pipeline` manager function calls each agent in sequence and passes all results to the Remediation Agent.

![Reliability comparison across all datasets](images/reliability_comparison.png)

### Environment

To reproduce this project, install the required libraries with:

```bash
pip install pandas numpy matplotlib seaborn requests
```

No GPU or special hardware is required. Tested with Python 3.14.2 on macOS. The optional LLM integration requires either [Ollama](https://ollama.com) running locally with a `llama3` model, or a `GROQ_API_KEY` environment variable set with access to `mixtral-8x7b-32768`.

---

## Section 3 — Experimental Design

We ran the pipeline on four datasets to validate the system across different levels of data quality and different real-world structures.

**Experiment 1 — Synthetic clean dataset (Dataset 1)**
- Purpose: verify that the pipeline correctly identifies minor issues in a nearly clean dataset and produces a high reliability score
- Baseline: manual inspection of the dataset
- Metrics: reliability score, per-agent scores, number of issues detected, number of suggestions generated

**Experiment 2 — Synthetic messy dataset (Dataset 2)**
- Purpose: verify that the pipeline correctly identifies severe quality problems (type mismatches, many missing values, extreme outliers) and produces a significantly lower reliability score than Dataset 1
- Baseline: Dataset 1 results
- Metrics: same as Experiment 1

**Experiment 3 — Real NoiPA dataset: Spesa (Dataset 3)**
- Purpose: test the pipeline on actual NoiPA payroll and tax spending data to verify it scales to real-world inputs and catches genuine data quality issues
- Baseline: synthetic dataset results
- Metrics: same as above, plus number of real duplicate rows and outliers detected

**Experiment 4 — Real NoiPA dataset: Attivazioni e Cessazioni (Dataset 4)**
- Purpose: verify the pipeline generalises across datasets with a structurally different set of columns (employee activations and terminations per ministry and region)
- Baseline: Dataset 3 results
- Metrics: same as above

---

## Section 4 — Results

| Dataset | Schema | Completeness | Consistency | Anomaly | Reliability |
|---------|--------|--------------|-------------|---------|-------------|
| Dataset 1 (synthetic, clean) | 95 | 93.33 | 95 | 100 | 95.50 |
| Dataset 2 (synthetic, messy) | 90 | 58.33 | 95 | 100 | 84.00 |
| Dataset 3 (real, Spesa) | 45 | 87.36 | 0 | 0 | 35.21 |
| Dataset 4 (real, Attivazioni) | 25 | 87.56 | 0 | 0 | 31.27 |

The results confirm that the system correctly assigns higher reliability scores to cleaner datasets and lower scores to messier ones. On the real NoiPA datasets, the agents detected thousands of genuine issues: 17,162 missing values and 216 numerical outliers in the Spesa dataset, and 47,503 missing values and 201 outliers in the Attivazioni dataset.

### Missing values per column

![Missing values Dataset 1](images/missing_values_dataset1.png)
![Missing values Dataset 2](images/missing_values_dataset2.png)
![Missing values Dataset 3 (Spesa)](images/missing_values_spesa.png)
![Missing values Dataset 4 (Attivazioni)](images/missing_values_attivazioni.png)

### Reliability score breakdown per agent

![Reliability Dataset 1](images/reliability_dataset1.png)
![Reliability Dataset 2](images/reliability_dataset2.png)
![Reliability Dataset 3 (Spesa)](images/reliability_spesa.png)
![Reliability Dataset 4 (Attivazioni)](images/reliability_attivazioni.png)

### Overall comparison

![Reliability comparison across all datasets](images/reliability_comparison.png)

---

## Section 5 — Conclusions

This project successfully built a modular multi-agent data quality system entirely in Python, without requiring any external services to function. The system automatically detects, reports, and fixes data quality issues across datasets of different sizes and structures. Testing on both synthetic and real NoiPA datasets confirmed that the agents behave correctly: clean datasets receive high reliability scores, while datasets with genuine problems receive appropriately low scores with detailed suggestions for improvement.

The key takeaway is that a multi-agent architecture is well-suited for data quality tasks because each type of check (schema, completeness, consistency, anomaly) is independent and can be developed, tested, and improved in isolation without affecting the others. The modular design also makes it straightforward to add new agents in the future.

Several limitations remain. The statistical checks are relatively simple — Z-scores assume normally distributed data, which may not hold for government spending figures. The cross-column validation rules are currently limited to the `Rata` column format and could be extended to cover more domain-specific logic. The categorical anomaly detection flags a very large number of rare values in real datasets, which may include false positives. Future work could include a Streamlit graphical interface for interactive exploration of the quality report, more sophisticated anomaly detection methods such as Isolation Forest, deeper LLM integration for automatic schema inference, and support for non-CSV formats such as JSON and relational databases.
