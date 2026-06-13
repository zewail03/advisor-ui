-- Add 20 CH of University Requirements (gen-ed) to the AIS program. 2026-06-13.
-- Backup: backend/aiu_pre_gened.dump
\set ON_ERROR_STOP on
BEGIN;

-- ===== 1. The 17 gen-ed courses (category 4 = University, major_code 'UNI') =====
INSERT INTO courses (code, name, credits, lab_hours, lecture_hours, tutorial_hours, other_hours, swl_hours, category_id, major_code, description) VALUES
 ('PSC101','Introduction to Law and Human Rights',0,0,2,0,0,0,4,'UNI','Introduction to Law and Human Rights.'),
 ('LAN022','English Language 1',0,0,2,0,0,0,4,'UNI','Elementary English course covering speaking, reading, writing and listening skills to construct accurate complex sentences and enhance communicative skills.'),
 ('GEO217','Climate Change and Sustainability',2,0,2,0,0,100,4,'UNI','Climate change definitions, drivers, impacts and UN policies. Global warming impacts on Egypt covering water resources, agriculture, tourism and population.'),
 ('LAN111','English Language 2',2,0,2,0,0,100,4,'UNI','Provides skills for different types of English writing, producing texts free of spelling, grammar and verbatim errors with proper use of punctuation.'),
 ('LAN130','French Language',2,0,2,0,0,100,4,'UNI','Develops student writing, reading and conversation skills in French to handle simple everyday life situations.'),
 ('CSE013','Introduction to Information Systems & Technology',2,0,2,0,0,100,4,'UNI','Introduction to information systems, computer hardware, data resource management, telecommunications, networks, and electronic business and commerce systems.'),
 ('MGT222','Entrepreneurship and Innovation',2,0,2,0,0,100,4,'UNI','Covers small business opportunities, entrepreneur characteristics, business ideas, creativity, feasibility, business plans, marketing, and finance.'),
 ('LAN114','Artistic Appreciation',2,0,2,0,0,100,4,'UNI','History of philosophy of beauty through civilizations, aesthetics in fine arts and literature, human aesthetic requirements, and art schools and intellectual trends.'),
 ('LIB116','Research and Analysis Skills',2,0,2,0,0,100,4,'UNI','Introduces research ethics, types of misconduct, information sources, web search tools, international databases, research article types, and scientific writing basics.'),
 ('LAN112','Critical Thinking',2,0,2,0,0,100,4,'UNI','Covers critical thinking definition, thinking habits, truth and knowledge, inductive and deductive reasoning, evaluating claims, consistency, and scientific reasoning.'),
 ('PHS071','Health and Livability',2,0,2,0,0,100,4,'UNI','Introduction to health and livability, principles of public health, epidemiology, social determinants, planning for health, and measuring livable cities.'),
 ('PSC207','Contemporary International Issues',2,0,2,0,0,100,4,'UNI','Overview of contemporary international issues and global political developments.'),
 ('MGT201','Negotiation Skills',2,0,2,0,0,100,4,'UNI','Covers negotiation introduction, preparation, actual negotiation stages, strategies, countering manipulation and psychological pressure, and post-negotiation review.'),
 ('MGT102','Strategic Planning (for non-Business Students)',2,0,2,0,0,100,4,'UNI','Holistic perspective of planning and development, strategies, planning types, SWOT analysis, strategic management, and Egypt sustainable development plan 2030.'),
 ('ADL123','First Aid',2,0,2,0,0,100,4,'UNI','Fundamentals of medical emergency management including first aid definition, cleaning cuts, treating burns, relieving heat stress, and basic emergency response skills.'),
 ('MGT121','Introduction to Management (for non-Business Students)',2,0,2,0,0,100,4,'UNI','Management foundations covering planning, organizing, leading, controlling, decision making, ethics, corporate social responsibility, and human resource management.'),
 ('LAN211','Academic Writing',2,0,2,0,0,100,4,'UNI','Develops academic writing skills including research papers, literature reviews, paraphrasing, summarizing, citing sources, argumentation, and logical structure.');

-- ===== 2. Two AIS requirement groups =====
INSERT INTO requirement_groups (program_id, name, course_code, course_name, description, min_courses, min_credits, major_id) VALUES
 (1,'University Required','','','All required university courses (incl. 2 zero-credit pass/fail)',10,16,1),
 (1,'University Elective','','','University elective basket - pick 2 of 7',2,4,1);

-- ===== 3. Link courses to groups (10 required + 7 elective) =====
INSERT INTO requirement_group_courses (program_id, major_id, major_code, group_name, course_code, course_name, is_required, required_year, required_semester) VALUES
 (1,1,'AIS','University Required','LAN022','English Language 1',true,1,1),
 (1,1,'AIS','University Required','PSC101','Introduction to Law and Human Rights',true,1,1),
 (1,1,'AIS','University Required','CSE013','Introduction to Information Systems & Technology',true,1,1),
 (1,1,'AIS','University Required','LAN111','English Language 2',true,1,2),
 (1,1,'AIS','University Required','LAN112','Critical Thinking',true,1,2),
 (1,1,'AIS','University Required','LAN114','Artistic Appreciation',true,2,1),
 (1,1,'AIS','University Required','LIB116','Research and Analysis Skills',true,2,1),
 (1,1,'AIS','University Required','GEO217','Climate Change and Sustainability',true,2,2),
 (1,1,'AIS','University Required','LAN130','French Language',true,2,2),
 (1,1,'AIS','University Required','MGT222','Entrepreneurship and Innovation',true,3,1),
 (1,1,'AIS','University Elective','PHS071','Health and Livability',false,3,1),
 (1,1,'AIS','University Elective','PSC207','Contemporary International Issues',false,3,1),
 (1,1,'AIS','University Elective','MGT201','Negotiation Skills',false,3,1),
 (1,1,'AIS','University Elective','MGT102','Strategic Planning (for non-Business Students)',false,3,2),
 (1,1,'AIS','University Elective','ADL123','First Aid',false,3,2),
 (1,1,'AIS','University Elective','MGT121','Introduction to Management (for non-Business Students)',false,3,2),
 (1,1,'AIS','University Elective','LAN211','Academic Writing',false,3,2);

-- ===== 4. Program total 113 -> 133 =====
UPDATE programs SET total_credits = 133 WHERE program_id = 1;

COMMIT;
