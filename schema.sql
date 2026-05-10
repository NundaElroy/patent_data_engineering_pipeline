-- schema.sql
DROP TABLE IF EXISTS relationships;
DROP TABLE IF EXISTS patents;
DROP TABLE IF EXISTS inventors;
DROP TABLE IF EXISTS companies;

CREATE TABLE patents (
    patent_id   VARCHAR(20) PRIMARY KEY,
    title       TEXT,
    abstract    TEXT,
    filing_date DATE, 
    year        INTEGER
);

CREATE TABLE inventors (
    inventor_id VARCHAR(20) PRIMARY KEY,
    name        VARCHAR(255),
    country     VARCHAR(10)
);

CREATE TABLE companies (
    company_id  VARCHAR(20) PRIMARY KEY,
    name        VARCHAR(255)
);

CREATE TABLE relationships (
    patent_id   VARCHAR(20),
    inventor_id VARCHAR(20),
    company_id  VARCHAR(20),
    FOREIGN KEY (patent_id)   REFERENCES patents(patent_id),
    FOREIGN KEY (inventor_id) REFERENCES inventors(inventor_id),
    FOREIGN KEY (company_id)  REFERENCES companies(company_id)
);

CREATE INDEX idx_patents_year  ON patents(year);
CREATE INDEX idx_inventors     ON relationships(inventor_id);
CREATE INDEX idx_companies     ON relationships(company_id);




CREATE TABLE IF NOT EXISTS cpc (
    patent_id   VARCHAR(20),
    cpc_section VARCHAR(10),
    cpc_type    VARCHAR(36),
    FOREIGN KEY (patent_id) REFERENCES patents(patent_id)
);

CREATE INDEX IF NOT EXISTS idx_cpc_patent  ON cpc(patent_id);
CREATE INDEX IF NOT EXISTS idx_cpc_section ON cpc(cpc_section);


CREATE TABLE IF NOT EXISTS cpc_detail (
    patent_id    VARCHAR(20),
    cpc_subclass VARCHAR(20),
    cpc_section  VARCHAR(10),
    FOREIGN KEY (patent_id) REFERENCES patents(patent_id)
);

CREATE INDEX IF NOT EXISTS idx_cpc_detail_patent   ON cpc_detail(patent_id);
CREATE INDEX IF NOT EXISTS idx_cpc_detail_subclass ON cpc_detail(cpc_subclass);
CREATE INDEX IF NOT EXISTS idx_cpc_detail_section  ON cpc_detail(cpc_section);

CREATE TABLE IF NOT EXISTS patent_citations (
    patent_id       VARCHAR(20),
    citation_count  INTEGER,
    FOREIGN KEY (patent_id) REFERENCES patents(patent_id)
);

CREATE INDEX IF NOT EXISTS idx_citations_patent  ON patent_citations(patent_id);
CREATE INDEX IF NOT EXISTS idx_citations_count   ON patent_citations(citation_count);