CREATE TABLE hospitals (
    hospital_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    inn VARCHAR(12) UNIQUE NOT NULL,
    address TEXT NOT NULL
);

CREATE TABLE positions (
    position_id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE departments (
    department_id SERIAL PRIMARY KEY,
    hospital_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    head_of_department VARCHAR(255) NOT NULL,
    FOREIGN KEY (hospital_id) REFERENCES hospitals(hospital_id) ON DELETE CASCADE
);

CREATE TABLE diagnoses (
    diagnosis_id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    treatment_method TEXT NOT NULL
);

CREATE TABLE doctors (
    doctor_id SERIAL PRIMARY KEY,
    hospital_id INT NOT NULL,
    department_id INT NOT NULL,
    position_id INT NOT NULL,
    inn VARCHAR(12) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    FOREIGN KEY (hospital_id) REFERENCES hospitals(hospital_id) ON DELETE CASCADE,
    FOREIGN KEY (department_id) REFERENCES departments(department_id) ON DELETE CASCADE,
    FOREIGN KEY (position_id) REFERENCES positions(position_id) ON DELETE RESTRICT
);

CREATE TABLE patients (
    patient_id SERIAL PRIMARY KEY,
    hospital_id INT NOT NULL,
    department_id INT NOT NULL,
    doctor_id INT NOT NULL,
    diagnosis_id INT NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    inn VARCHAR(12) UNIQUE,
    admission_date DATE DEFAULT CURRENT_DATE,
    diagnosis_date DATE,
    discharge_date DATE,
    discharge_status VARCHAR(100),
    FOREIGN KEY (hospital_id) REFERENCES hospitals(hospital_id) ON DELETE CASCADE,
    FOREIGN KEY (department_id) REFERENCES departments(department_id) ON DELETE CASCADE,
    FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id) ON DELETE RESTRICT,
    FOREIGN KEY (diagnosis_id) REFERENCES diagnoses(diagnosis_id) ON DELETE RESTRICT,
    CHECK (discharge_date >= admission_date)
);
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public';