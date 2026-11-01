import { ArrowUpLeft } from 'lucide-react';
import { Link } from 'react-router-dom';

export default function NotFound() {
  return <div className="not-found"><span>404</span><h1>الصفحة غير موجودة</h1><Link to="/" className="button button-primary">العودة إلى النظرة العامة <ArrowUpLeft size={16} /></Link></div>;
}
