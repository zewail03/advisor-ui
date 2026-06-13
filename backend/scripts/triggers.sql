-- ============================================================
-- Database triggers for automatic CGPA/standing/seat maintenance
-- Apply after tables are created. Run against Postgres only.
-- ============================================================

-- Trigger 1: Recalculate CGPA + completed credits when a grade changes
CREATE OR REPLACE FUNCTION update_cgpa()
RETURNS TRIGGER AS $$
DECLARE
    v_student_id TEXT;
    v_cgpa FLOAT;
    v_total_credits INT;
BEGIN
    SELECT e.student_id INTO v_student_id
    FROM enrollments e
    WHERE e.id = NEW.enrollment_id;

    SELECT
        COALESCE(
            SUM(g.grade_points * c.credit_hours)
            / NULLIF(
                SUM(CASE WHEN g.grade_points IS NOT NULL THEN c.credit_hours ELSE 0 END), 0
            ),
            0.0
        ),
        COALESCE(
            SUM(CASE WHEN g.letter_grade NOT IN ('W','I','S','U') THEN c.credit_hours ELSE 0 END),
            0
        )
    INTO v_cgpa, v_total_credits
    FROM grades g
    JOIN enrollments e ON g.enrollment_id = e.id
    JOIN sections s ON e.section_id = s.id
    JOIN courses c ON s.course_id = c.id
    WHERE e.student_id = v_student_id
      AND g.grade_points IS NOT NULL;

    UPDATE academic_standing
    SET cgpa = v_cgpa,
        completed_credit_hours = v_total_credits,
        last_updated = NOW()
    WHERE student_id = v_student_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS after_grade_change ON grades;
CREATE TRIGGER after_grade_change
AFTER INSERT OR UPDATE ON grades
FOR EACH ROW EXECUTE FUNCTION update_cgpa();


-- Trigger 2: Update academic standing when CGPA changes
CREATE OR REPLACE FUNCTION update_standing()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.cgpa >= 2.0 THEN
        NEW.standing := 'good';
        NEW.consecutive_probation_semesters := 0;
    ELSIF NEW.cgpa < 2.0 AND OLD.cgpa >= 2.0 THEN
        NEW.standing := 'probation';
        NEW.consecutive_probation_semesters := 1;
    ELSIF NEW.cgpa < 2.0 AND OLD.cgpa < 2.0 THEN
        NEW.consecutive_probation_semesters := COALESCE(OLD.consecutive_probation_semesters, 0) + 1;
        IF NEW.consecutive_probation_semesters >= 2 THEN
            NEW.standing := 'dismissal_risk';
        ELSE
            NEW.standing := 'probation';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS after_standing_update ON academic_standing;
CREATE TRIGGER after_standing_update
BEFORE UPDATE OF cgpa ON academic_standing
FOR EACH ROW EXECUTE FUNCTION update_standing();


-- Trigger 3: Maintain enrolled_count on sections
CREATE OR REPLACE FUNCTION maintain_enrolled_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' AND NEW.status = 'Enrolled' THEN
        UPDATE sections SET enrolled_count = enrolled_count + 1 WHERE id = NEW.section_id;
    ELSIF TG_OP = 'DELETE' AND OLD.status = 'Enrolled' THEN
        UPDATE sections SET enrolled_count = GREATEST(0, enrolled_count - 1) WHERE id = OLD.section_id;
    ELSIF TG_OP = 'UPDATE' THEN
        IF OLD.status = 'Enrolled' AND NEW.status <> 'Enrolled' THEN
            UPDATE sections SET enrolled_count = GREATEST(0, enrolled_count - 1) WHERE id = NEW.section_id;
        ELSIF OLD.status <> 'Enrolled' AND NEW.status = 'Enrolled' THEN
            UPDATE sections SET enrolled_count = enrolled_count + 1 WHERE id = NEW.section_id;
        END IF;
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS after_enrollment_change ON enrollments;
CREATE TRIGGER after_enrollment_change
AFTER INSERT OR UPDATE OR DELETE ON enrollments
FOR EACH ROW EXECUTE FUNCTION maintain_enrolled_count();
