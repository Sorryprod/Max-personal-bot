export type QuestionType = 'yes_no' | 'choice' | 'text';

export interface QuestionDraft {
  text: string;
  qtype: QuestionType;
  options: string[];
  is_blocking: boolean;
  accepted: string[];
}

export interface Question extends QuestionDraft {
  id: number;
}

export interface Vacancy {
  id: number;
  position: string;
  schedule: string;
  salary_from: number | null;
  salary_to: number | null;
  address: string;
  status: 'active' | 'closed';
  invite_link: string;
  created_at: string | null;
  total: number;
  unreviewed: number;
  questions: Question[] | null;
}

export interface VacancyDraft {
  position: string;
  schedule: string;
  salary_from: string;
  salary_to: string;
  address: string;
  questions: QuestionDraft[];
}

export interface Me {
  user: { id: number; name: string };
  employer: { place_name: string; city: string } | null;
  question_templates: QuestionDraft[];
  max_questions: number;
}

export type ApplicationStatus = 'screened' | 'invited' | 'reserve' | 'rejected';

export interface AnswerView {
  question_id: number;
  value: string;
  display: string;
  passed: boolean;
}

export interface Slot {
  id: number;
  starts_at: string;
  is_chosen: boolean;
}

export interface Application {
  id: number;
  status: ApplicationStatus;
  screening_failed: boolean;
  created_at: string | null;
  name: string;
  contact: string;
  answers: AnswerView[];
  slots: Slot[];
}

export interface VacancyApplications {
  vacancy: Vacancy;
  applications: Application[];
}
