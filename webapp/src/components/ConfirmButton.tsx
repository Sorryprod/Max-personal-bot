import { useEffect, useState } from 'react';
import { Button } from '@maxhub/max-ui';
import type { ButtonProps } from '@maxhub/max-ui';

/** Кнопка для действий, о которых сразу узнаёт кандидат: первое нажатие просит подтверждения. */
export function ConfirmButton({ confirmText, onClick, children, ...props }: ButtonProps & { confirmText: string }) {
  const [armed, setArmed] = useState(false);
  useEffect(() => {
    if (!armed) return;
    const timer = setTimeout(() => setArmed(false), 3000);
    return () => clearTimeout(timer);
  }, [armed]);
  return (
    <Button
      {...props}
      variant={armed ? 'destructive' : props.variant}
      onClick={(e) => {
        if (armed) {
          setArmed(false);
          onClick?.(e);
        } else {
          setArmed(true);
        }
      }}
    >
      {armed ? confirmText : children}
    </Button>
  );
}
