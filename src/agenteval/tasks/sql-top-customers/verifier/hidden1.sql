CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL, amount REAL NOT NULL, status TEXT NOT NULL);
INSERT INTO customers VALUES (1,'Bob'),(2,'Ada'),(3,'Cy'),(4,'Dee'),(5,'Eve'),(6,'Fay, Jr.');
INSERT INTO orders VALUES
 (1,2,50.00,'completed'),(2,2,25.50,'completed'),(3,2,100.00,'cancelled'),
 (4,1,75.50,'completed'),
 (5,3,20.25,'completed'),(6,3,9.99,'completed'),
 (7,4,500.00,'cancelled'),
 (8,5,12.00,'completed'),
 (9,6,80.00,'completed'),(10,6,5.00,'refunded');
