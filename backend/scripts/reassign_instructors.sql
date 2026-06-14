-- Reassign instructor roster (2026-06-14)
-- Doctors: keep 10 existing (rename Sherif Hamdy -> Shereen Hamdy), add 5 new = 15 total; normalize "Dr. " spacing.
-- Engineers: remove all 12 existing, replace with 27 new names; normalize "Eng. " spacing.
-- "University Staff" placeholder (127 sections) is left untouched.
-- Instructor->section assignments are synthetic, so sections are spread deterministically by section_id.

BEGIN;

-- Doctors -> 15 normalized names
UPDATE sections
SET instructor_name = (ARRAY[
  'Dr. Ashraf Elsayed',
  'Dr. Mervat Mikhail',
  'Dr. Essam Abdelatif',
  'Dr. Abdelatif Mahmoud',
  'Dr. Shereen Hamdy',
  'Dr. Laila Shoukry',
  'Dr. Ahmed Shalaby',
  'Dr. Mohamed Elkholy',
  'Dr. Mostafa Elnainay',
  'Dr. Islam Elgedawy',
  'Dr. Emad Ashmawy',
  'Dr. Ahmed Younes',
  'Dr. Ali Abdelaziz',
  'Dr. Islam ElKabani',
  'Dr. Mohamed Abdou'
])[(section_id % 15) + 1]
WHERE instructor_name LIKE 'Dr.%';

-- Engineers -> 27 normalized names (all old Eng. names removed)
UPDATE sections
SET instructor_name = (ARRAY[
  'Eng. Abdelrahman Magdy',
  'Eng. Ahmed Yousry',
  'Eng. Eman Hamdy',
  'Eng. Ahmed Yahia',
  'Eng. Bardees Khaled',
  'Eng. Mohamed Ezzat',
  'Eng. Rania Ismail',
  'Eng. Mohamed Elredeny',
  'Eng. Nermeen Elhendy',
  'Eng. Fatma Muhammad',
  'Eng. Hythem Ahmed',
  'Eng. Tasneem Abdelaziz',
  'Eng. Heba Allah Amr',
  'Eng. Mohamed Sobhy',
  'Eng. Sara Elkhrashy',
  'Eng. Menna Allah Samy',
  'Eng. Nourhan Abdallah',
  'Eng. Sarah Gamal',
  'Eng. Rowan Essam',
  'Eng. Eman Hendawy',
  'Eng. Mayar Ayman',
  'Eng. Mahmoud Abo Zithar',
  'Eng. Mariam Alaa',
  'Eng. Ahmed Fayez',
  'Eng. Hosna Sayed',
  'Eng. Mariam Zaki',
  'Eng. Ahmed Shoukry'
])[(section_id % 27) + 1]
WHERE instructor_name LIKE 'Eng.%';

COMMIT;
