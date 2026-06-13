-- Trim dataset 2026-06-13: drop the AIE / Computer-Engineering program (program_id=2,
-- major AIE, 180 students) and remove 35 courses. Single transaction; rolls back on error.
-- Backup taken first: backend/aiu_pre_trim.dump (pg_restore).
\set ON_ERROR_STOP on
BEGIN;

-- ========== PART 1: DROP THE AIE / COMPUTER-ENGINEERING PROGRAM ==========
-- NO-ACTION children of students must be removed before the students.
DELETE FROM academic_standing
 WHERE student_code IN (SELECT student_code FROM students WHERE program_id = 2);
DELETE FROM advisor_assignments
 WHERE student_code IN (SELECT student_code FROM students WHERE program_id = 2);
-- 180 AIE students. CASCADE clears enrollments->grades, financials, chat->messages,
-- petitions, capstone->milestones, evaluations, retakes, waitlist, notifications, approvals.
DELETE FROM students WHERE program_id = 2;
-- AIE requirement structure + the program/major rows themselves.
DELETE FROM requirement_group_courses WHERE program_id = 2;
DELETE FROM requirement_groups        WHERE program_id = 2;
DELETE FROM majors   WHERE major_id   = 3;
DELETE FROM programs WHERE program_id = 2;

-- ========== PART 2: DELETE THE 35 COURSES ==========
-- Deleting sections CASCADES to section_meetings, enrollments->grades, waitlist.
DELETE FROM sections WHERE course_code IN (
  'CSE411','CSE485','CSE487','CSE488','AIE342','AIE343','AIE424','AIE426','AIE427','AIE444',
  'CSE271','CSE272','CSE322','CSE475','AIE452','AIE453','AIE454','AIE455','AIE456','AIE457',
  'CSE113','CSE335','ELE115','ELE215','ELE232','ELE233','ELE338','ELE432','MAT121','MAT122',
  'MAT123','AIE315','AIE316','AIE392','CSE446');

DELETE FROM prerequisites WHERE course_code IN (
  'CSE411','CSE485','CSE487','CSE488','AIE342','AIE343','AIE424','AIE426','AIE427','AIE444',
  'CSE271','CSE272','CSE322','CSE475','AIE452','AIE453','AIE454','AIE455','AIE456','AIE457',
  'CSE113','CSE335','ELE115','ELE215','ELE232','ELE233','ELE338','ELE432','MAT121','MAT122',
  'MAT123','AIE315','AIE316','AIE392','CSE446')
   OR prerequisite_course_code IN (
  'CSE411','CSE485','CSE487','CSE488','AIE342','AIE343','AIE424','AIE426','AIE427','AIE444',
  'CSE271','CSE272','CSE322','CSE475','AIE452','AIE453','AIE454','AIE455','AIE456','AIE457',
  'CSE113','CSE335','ELE115','ELE215','ELE232','ELE233','ELE338','ELE432','MAT121','MAT122',
  'MAT123','AIE315','AIE316','AIE392','CSE446');

DELETE FROM requirement_group_courses WHERE course_code IN (
  'CSE411','CSE485','CSE487','CSE488','AIE342','AIE343','AIE424','AIE426','AIE427','AIE444',
  'CSE271','CSE272','CSE322','CSE475','AIE452','AIE453','AIE454','AIE455','AIE456','AIE457',
  'CSE113','CSE335','ELE115','ELE215','ELE232','ELE233','ELE338','ELE432','MAT121','MAT122',
  'MAT123','AIE315','AIE316','AIE392','CSE446');

DELETE FROM course_embeddings WHERE course_code IN (
  'CSE411','CSE485','CSE487','CSE488','AIE342','AIE343','AIE424','AIE426','AIE427','AIE444',
  'CSE271','CSE272','CSE322','CSE475','AIE452','AIE453','AIE454','AIE455','AIE456','AIE457',
  'CSE113','CSE335','ELE115','ELE215','ELE232','ELE233','ELE338','ELE432','MAT121','MAT122',
  'MAT123','AIE315','AIE316','AIE392','CSE446');

DELETE FROM courses WHERE code IN (
  'CSE411','CSE485','CSE487','CSE488','AIE342','AIE343','AIE424','AIE426','AIE427','AIE444',
  'CSE271','CSE272','CSE322','CSE475','AIE452','AIE453','AIE454','AIE455','AIE456','AIE457',
  'CSE113','CSE335','ELE115','ELE215','ELE232','ELE233','ELE338','ELE432','MAT121','MAT122',
  'MAT123','AIE315','AIE316','AIE392','CSE446');

COMMIT;
