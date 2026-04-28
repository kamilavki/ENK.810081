# ENK.810081
# Reply: Agents for Data Quality
**Team Members:** Nurkhanym Ziyabek (810081), Emanuele Aicardi (814361), Kamila Dochshanova (809891)

## Introduction
This project solves the crucial task of automated data quality assurance within the NoiPA dataset ecosystem. We are developing a multi-agent system designed to autonomously identify, analyze, and report on structural and content-related inconsistencies. By simulating professional data management workflows, our system ensures that datasets conform to predefined schemas and maintain a high level of completeness before being used for subsequent analytics 

## Methods
The system is composed of five specialized agents, each responsible for a specific type of data quality check, orchestrated by a central run_pipeline function:

1. Schema Agent — validates column naming conventions (special characters, leading digits, whitespace) and detects mixed data types within columns (e.g. a numeric column containing strings). Returns a schema score out of 100.
2. Completeness Agent — counts missing values and placeholder strings (e.g. "N/A", "-", "unknown") per column, computes a completeness percentage, and flags sparse columns where more than 50% of values are missing. Returns a completeness score out of 100.
3. Consistency Agent — detects exact duplicate rows, flags inconsistent string casing within the same column, and checks cross-column logical rules (e.g. the Rata column must follow the YYYYMM format). Returns a consistency score out of 100.
4. Anomaly Agent — applies Z-score analysis to detect numerical outliers (values more than 3 standard deviations from the mean) and flags rare categorical values appearing less than 1% of the time. Returns an anomaly score out of 100.
5. Remediation Agent — aggregates findings from all agents, generates concrete actionable suggestions for each issue, and computes a final weighted reliability score:
Reliability=0.2×Schema+0.3×Completeness+0.3×Consistency+0.2×Anomaly

An LLM integration (local Ollama or Groq API) can enhance the natural language output of the Remediation Agent. If neither is available, the system falls back to deterministic rule-based text generation automatically — the pipeline always runs completely.

A fix_dataset function automatically applies corrections: removing duplicates, imputing missing values (median for numeric columns, mode for categorical), standardizing string casing to title case, and capping outliers at ±3 standard deviations.


## Experimental Design
We ran the pipeline on four datasets to validate the system across different levels of data quality and different real-world structures.
Experiment 1 — Synthetic clean dataset (Dataset 1)

Purpose: verify that the pipeline correctly identifies minor issues in a nearly clean dataset and produces a high reliability score
Baseline: manual inspection of the dataset
Metrics: reliability score, per-agent scores, number of issues detected, number of suggestions generated

Experiment 2 — Synthetic messy dataset (Dataset 2)

Purpose: verify that the pipeline correctly identifies severe quality problems (type mismatches, many missing values, extreme outliers) and produces a low reliability score
Baseline: Dataset 1 results (comparison between clean and messy)
Metrics: same as Experiment 1 — the reliability score should drop significantly compared to Dataset 1

Experiment 3 — Real NoiPA dataset: Spesa (Dataset 3)

Purpose: test the pipeline on actual NoiPA payroll/tax spending data to verify it scales to real-world inputs and catches genuine issues
Baseline: Dataset 1 and 2 synthetic results
Metrics: same as above, plus number of real duplicate rows and outliers detected

Experiment 4 — Real NoiPA dataset: Attivazioni e Cessazioni (Dataset 4)

Purpose: verify the pipeline generalises across datasets with a different column structure (employee activations and terminations per ministry and region)
Baseline: Dataset 3 results
Metrics: same as above

## Results

| Dataset | Schema | Completeness | Consistency | Anomaly | Reliability |
|---------|--------|--------------|-------------|---------|-------------|
| Dataset1 | 100 | ~93 | ~85 | ~96 | ~91 |
| Dataset2 | ~75 | ~25 | ~65 | ~90 | ~59 |
| Dataset 3 | ~45 | ~62 | ~80 | ~70 | 35.21 |
| Dataset 4 | ~25 | ~55 | ~75 | ~68 | 31.27 |
## Conclusions
This project successfully built a modular multi-agent data quality system entirely in Python, without requiring any external services to function. The system automatically detects, reports, and fixes data quality issues across datasets of different sizes and structures. Testing on both synthetic and real NoiPA datasets confirmed that the agents behave correctly: clean datasets receive high reliability scores, while datasets with genuine problems receive appropriately low scores with detailed suggestions for improvement.
The key takeaway is that a multi-agent architecture is well-suited for data quality tasks because each type of check (schema, completeness, consistency, anomaly) is independent and can be developed, tested, and improved in isolation without affecting the others.
Several limitations remain. The statistical checks are relatively simple — Z-scores assume normally distributed data, which may not hold for government spending figures. The cross-column validation rules are currently limited to the Rata column format and could be extended to cover more domain-specific logic. The categorical anomaly detection flags a very large number of rare values in real datasets, which may include false positives. Future work could include a Streamlit graphical interface for interactive exploration of the quality report, more sophisticated anomaly detection methods such as Isolation Forest, deeper LLM integration for automatic schema inference, and support for non-CSV formats such as JSON and relational databases.
