import { CheckData } from '@/features/check-data/ui/CheckData';
import { FolderField } from '@/features/pick-folder/ui/FolderField';
import { useSettings } from '@/features/train-settings/model/store';
import { go } from '@/shared/lib/route';
import { HelpButton } from '@/shared/ui/help';
import { PageHead } from '@/shared/ui/PageHead';

export function DataPage() {
  const s = useSettings();
  return (
    <section>
      <PageHead step="Шаг 1 из 4" title="Откуда взять фотографии">
        Рядом с каждым фото .jpg должна лежать маска .png с тем же именем: на ней закрашена ржавчина. Укажите три папки.
      </PageHead>
      <div className="card">
        <FolderField title="Для обучения" help="train" hint="Папка train. Здесь программа учится. Обычно это 70–80% всех снимков."
          value={s.train_dir} onChange={(v) => s.set({ train_dir: v })} />
        <FolderField title="Для проверки в ходе обучения" help="valid" hint="Папка valid. Эти снимки программа не видит при обучении, на них она сверяется после каждого прохода."
          value={s.valid_dir} onChange={(v) => s.set({ valid_dir: v })} />
        <FolderField title="Для итоговой оценки" help="test" optional hint="Папка test. Используется один раз в конце. Можно оставить пустой."
          value={s.test_dir} onChange={(v) => s.set({ test_dir: v })} />
        <div className="field">
          <div className="lbl">Название эксперимента<HelpButton topic="run" /></div>
          <div className="hint">По названию вы потом найдёте результат. Например: «кофе_384_25эпох».</div>
          <div className="path">
            <input className="in" style={{ maxWidth: 320, flex: 'none' }} value={s.run_name} onChange={(e) => s.set({ run_name: e.target.value })} aria-label="Название эксперимента" />
          </div>
        </div>
      </div>
      <div style={{ marginTop: 18 }}>
        <CheckData train={s.train_dir} valid={s.valid_dir} test={s.test_dir} />
      </div>
      <div className="pbar"><span /><button className="btn primary big" type="button" onClick={() => go('params')}>Далее: параметры →</button></div>
    </section>
  );
}
