import { useEffect } from 'react';
import { useExperiments } from '@/entities/experiment/model/store';
import { useTraining } from '@/entities/training/model/store';
import { useSession } from '@/entities/session/model/store';
import { LoginForm } from '@/features/login/ui/LoginForm';
import { CheckPage } from '@/pages/check/ui/CheckPage';
import { DataPage } from '@/pages/data/ui/DataPage';
import { HomePage } from '@/pages/home/ui/HomePage';
import { ParamsPage } from '@/pages/params/ui/ParamsPage';
import { ResultsPage } from '@/pages/results/ui/ResultsPage';
import { TrainPage } from '@/pages/train/ui/TrainPage';
import { useRoute } from '@/shared/lib/route';
import { HelpModal } from '@/shared/ui/help';
import { Sidebar } from '@/widgets/sidebar/ui/Sidebar';

const PAGES = { home: HomePage, data: DataPage, params: ParamsPage, train: TrainPage, results: ResultsPage, check: CheckPage };

export function App() {
  const route = useRoute();
  const load = useExperiments((s) => s.load);
  const attach = useTraining((s) => s.attach);

  const { checked, required, authed, check } = useSession();

  useEffect(() => { void check(); }, [check]);
  useEffect(() => {
    if (!checked || !authed) return;
    void load();
    void attach();
  }, [checked, authed, load, attach]);

  if (!checked) return null;
  if (required && !authed) return <LoginForm />;

  const Page = PAGES[route];
  return (
    <div className="app">
      <Sidebar route={route} />
      <main className="main"><Page /></main>
      <HelpModal />
    </div>
  );
}
