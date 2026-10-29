cat > query.sql <<'EOF'
SELECT c.name AS name, ROUND(SUM(o.amount), 2) AS total
FROM customers c JOIN orders o ON o.customer_id = c.id
WHERE o.status = 'completed'
GROUP BY c.id, c.name ORDER BY total DESC LIMIT 3;
EOF
