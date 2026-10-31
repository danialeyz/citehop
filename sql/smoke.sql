-- Session-local data only; does not create the C03 corpus schema.
CREATE TEMPORARY TABLE c01_vector_smoke (id INT PRIMARY KEY, embedding VECTOR(3));
INSERT INTO c01_vector_smoke VALUES (1, VEC_FromText('[1,0,0]'));
SELECT id, VEC_DISTANCE_COSINE(embedding, VEC_FromText('[1,0,0]')) AS distance
FROM c01_vector_smoke;
