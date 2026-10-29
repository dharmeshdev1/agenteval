cat > query.sql <<'EOF'
SELECT c.name AS customer, ROUND(SUM(o.amount), 2) AS spend
FROM customers c JOIN orders o ON o.customer_id = c.id
WHERE o.status = 'completed'
GROUP BY c.id, c.name ORDER BY spend DESC, customer ASC LIMIT 5;
EOF
