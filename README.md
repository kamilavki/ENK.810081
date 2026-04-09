# ENK.810081
# Reply: Agents for Data Quality
**Team Members:** Nurkhanym Ziyabek (810081), Emanuele Aicardi (814361), Kamila Dochshanova (809891)

## Introduction
This project solves the crucial task of automated data quality assurance within the NoiPA dataset ecosystem. We are developing a multi-agent system designed to autonomously identify, analyze, and report on structural and content-related inconsistencies. By simulating professional data management workflows, our system ensures that datasets conform to predefined schemas and maintain a high level of completeness before being used for subsequent analytics 

## Methods
Our architecture follows a modular Multi-Agent design. This choice was made to ensure scalability, each agent acts as a specialist for a specific validation phase:  
Schema Agent: Validates data types and naming conventions against a JSON-defined schema. 
Completeness Agent: Implements a robust detection algorithm that scans for standard `NaNs` and domain-specific placeholders ('unknown', 'n/a' and etc).


## Experimental Design
* **The main purpose:** Experiments confirm the system's ability to detect non-standard missing values and structural deviations in administrative datasets.
* **Baseline(s):** We used the standard tools of the Pandas library as a Baseline. However, we found that the usual methods do not cope with real administrative data: they do not see gaps hidden behind characters like "-" or the words "unknown". Our Completeness Agent surpasses this baseline because it uses advanced detection logic.
* **Evaluation Metrics(s):** Completeness Rate : Measured as $((Total - Detected\_Missings) / Total) \times 100$.
* Schema Compliance Score: A binary/percentage metric indicating how many columns match the schema.json definition.

## Results
* **Main finding(s):** ...

## Conclusions
* **Take-away:** The implementation of a specialized multi-agent system significantly increases the reliability of data management. By automating stage 1 and stage 2, we reduce the number of human errors in data auditing and provide a transparent, reproducible framework for evaluating the health of a dataset in a professional environment. While our current system provides a solid foundation for detection, the next stage involves fully automating the remediation phase (phase 5) by implementing an agent capable of generating offline remediation suggestions. In addition, we plan to improve the consistency agent (phase 3) to perform column-by-column due diligence and integrate anomaly detection (phase 4) to identify statistical deviations and rare categorical anomalies that may signal errors in data entry.
