CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL, amount REAL NOT NULL, status TEXT NOT NULL);
INSERT INTO customers VALUES (1,'Zed'),(2,'Yan');
INSERT INTO orders VALUES (1,1,5.00,'completed'),(2,2,9.00,'cancelled');
