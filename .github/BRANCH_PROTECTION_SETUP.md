# Настройка Branch Protection для автоматического мерджа

## Требуемые изменения в GitHub Settings

Перейдите в: **Settings → Branches → Branch protection rules → Edit rule для main**

### Required status checks that must pass before merging

**УДАЛИТЕ** из списка required checks:
- ❌ `validate` (это старый check, который может блокировать мердж)

**ДОБАВЬТЕ** в список required checks:
- ✅ `validate-automated-complete` (для автоматических sync/cleanup PR) — **ВСЕГДА ПРОХОДИТ**
- ✅ `validate-manual-complete` (для ручных PR и WordPress/ITINAI submissions) — проходит только если валидация успешна

## Почему это важно

### Для автоматических PR (`codex/sync-external-agents`, `auto-cleanup-offline-agents`):
- Job `validate-automated-complete` **ВСЕГДА** проходит успешно (exit 0)
- Он зависит от `validate`, но игнорирует его результат
- Валидация выполняется, ошибки логируются, но мердж НЕ блокируется
- Auto-merge workflow автоматически смерджит PR после успеха этого check

### Для ручных PR и WordPress/ITINAI submissions:
- Job `validate-manual-complete` проходит только если реальная валидация успешна
- Это обеспечивает контроль качества для ручных изменений

## Альтернатива: Использовать разные правила для разных путей

Если вы хотите разделить правила для разных типов PR, создайте два правила:

### Правило 1: Для автоматических sync PR
- **Branch name pattern**: `codex/sync-external-agents|auto-cleanup-offline-agents`
- **Required status checks**: `validate-automated-complete`
- **Include administrators**: ❌ Нет

### Правило 2: Для всех остальных PR (main branch)
- **Branch name pattern**: `main`
- **Required status checks**: `validate-manual-complete`
- **Include administrators**: ✅ Да

## Проверка настройки

После настройки:
1. Создайте тестовый PR с ветки `codex/sync-external-agents`
2. Убедитесь что check `validate-automated-complete` появляется как required
3. Убедитесь что check `validate` НЕ является required для этого PR
4. После завершения workflow PR должен автоматически смерджиться

## Важно!

Если у вас уже настроен branch protection с check `validate`, вам нужно:
1. Зайти в Settings → Branches → Branch protection rules
2. Нажать Edit на правиле для main
3. В разделе "Check names" удалить `validate`
4. Добавить `validate-automated-complete` и `validate-manual-complete`
5. Сохранить изменения
