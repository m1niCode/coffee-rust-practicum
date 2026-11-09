import { useState } from 'react';
import { CheckData } from '@/features/check-data/ui/CheckData';
import { UploadField } from '@/features/upload-data/ui/UploadField';
import { useSettings } from '@/features/train-settings/model/store';
import { post } from '@/shared/api/client';
import { go } from '@/shared/lib/route';
import { HelpButton } from '@/shared/ui/help';
import { PageHead } from '@/shared/ui/PageHead';

export function DataPage() {
  const s = useSettings();
  const [version, setVersion] = useState(0);
  const bump = () => setVersion((v) => v + 1);
  const clear = (kind: 'train' | 'valid' | 'test') => async () => { await post('/data/clear', { kind }); bump(); };
  return (
    <section>
      <PageHead step="Шаг 1 из 4" title="Загрузите фотографии">
        Рядом с каждым фото .jpg должна лежать маска .png с тем же именем: на ней закрашена ржавчина.
        Файлы загружаются на сервер и видны только вам.
      </PageHead>
      <div className="card">
        <UploadField kind="auto" title="Всё сразу одним архивом"
          hint="Zip-архив, внутри которого папки train, valid и (по желанию) test. Так быстрее всего." onDone={bump} />
        <UploadField kind="train" title="Для обучения" help="train" hint="Здесь программа учится. Обычно это 70–80% всех снимков. Можно выбрать фото и маски вместе или zip."
          onDone={bump} onClear={clear('train')} />
        <UploadField kind="valid" title="Для проверки в ходе обучения" help="valid" hint="Эти снимки программа не видит при обучении, на них она сверяется после каждого прохода."
          onDone={bump} onClear={clear('valid')} />
        <UploadField kind="test" title="Для итоговой оценки" help="test" optional hint="Используется один раз в конце. Можно не загружать."
          onDone={bump} onClear={clear('test')} />
        <div className="field">
          <div className="lbl">Название эксперимента<HelpButton topic="run" /></div>
          <div className="hint">По названию вы потом найдёте результат. Например: «кофе_384_25эпох».</div>
          <div className="path">
            <input className="in" style={{ maxWidth: 320, flex: 'none' }} value={s.run_name} onChange={(e) => s.set({ run_name: e.target.value })} aria-label="Название эксперимента" />
          </div>
        </div>
      </div>
      <div style={{ marginTop: 18 }}>
        <CheckData refresh={version} />
      </div>
      <div className="pbar"><span /><button className="btn primary big" type="button" onClick={() => go('params')}>Далее: параметры →</button></div>
    </section>
  );
}
