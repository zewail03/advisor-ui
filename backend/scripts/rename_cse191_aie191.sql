-- Align Field Training 1 to the official AIS study plan: CSE191 -> AIE191. 2026-06-13.
-- code is the PK referenced by sections/prerequisites/requirement_group_courses/embeddings,
-- so: create AIE191, repoint all references, delete CSE191 (immediate FK checks stay satisfied).
\set ON_ERROR_STOP on
BEGIN;

INSERT INTO courses (code, name, credits, lab_hours, lecture_hours, tutorial_hours, other_hours, swl_hours, category_id, major_code, description)
SELECT 'AIE191', 'Field Training 1 in AI Science', credits, lab_hours, lecture_hours, tutorial_hours, other_hours, swl_hours, category_id, major_code,
       'Field training 1 in AI Science: supervised practical training applying AI/CS coursework in a professional setting.'
FROM courses WHERE code = 'CSE191';

UPDATE sections                  SET course_code = 'AIE191' WHERE course_code = 'CSE191';
UPDATE prerequisites             SET course_code = 'AIE191' WHERE course_code = 'CSE191';
UPDATE prerequisites             SET prerequisite_course_code = 'AIE191' WHERE prerequisite_course_code = 'CSE191';
UPDATE requirement_group_courses SET course_code = 'AIE191', course_name = 'Field Training 1 in AI Science' WHERE course_code = 'CSE191';
DELETE FROM course_embeddings    WHERE course_code = 'CSE191';

DELETE FROM courses WHERE code = 'CSE191';

COMMIT;
