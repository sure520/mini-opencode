import React from 'react';
import './{{ComponentName}}.css';

interface {{ComponentName}}Props {
  title: string;
  description?: string;
  className?: string;
}

export const {{ComponentName}}: React.FC<{{ComponentName}}Props> = ({
  title,
  description,
  className = '',
}) => {
  return (
    <div className={`{{component-name}} ${className}`}>
      <h2>{title}</h2>
      {description && <p>{description}</p>}
    </div>
  );
};

export default {{ComponentName}};
