CREATE TABLE corporate_training.assets (
    id INT PRIMARY KEY,
    asset_name VARCHAR(64) NOT NULL,
    owner_team VARCHAR(64) NOT NULL
);

INSERT INTO corporate_training.assets (id, asset_name, owner_team) VALUES
    (1, 'training-web-01', 'security-lab'),
    (2, 'training-files-01', 'security-lab');
