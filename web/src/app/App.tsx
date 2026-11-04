import { useEffect } from 'react';
import { useExperiments } from '@/entities/experiment/model/store';
import { useTraining } from '@/entities/training/model/store';
import { useSettings } from '@/features/train-settings/model/store';
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

  useEffect(() => {
    void load().then(() => {
      // по умолчанию папки данных лежат рядом с программой
      const base = useExperiments.getState().info?.base_dir;
      const s = useSettings.getState();
      if (base && !s.train_dir) {
        const sep = base.includes('\\') ? '\\' : '/';
        s.set({ train_dir: base + sep + 'train', valid_dir: base + sep + 'valid', test_dir: base + sep + 'test' });
      }
    });
    void attach();
  }, [load, attach]);

  const Page = PAGES[route];
  return (
    <div className="app">
      <Sidebar route={route} />
      <main className="main"><Page /></main>
      <HelpModal />
    </div>
  );
}
