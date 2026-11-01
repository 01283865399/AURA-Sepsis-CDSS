import { Component } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

export default class ErrorBoundary extends Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error('MediMind AI interface error', error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return <main className="fatal-error" role="alert"><AlertTriangle size={26} /><h1>تعذر عرض هذه الصفحة</h1><p>حدث خطأ في الواجهة. لم تُرسل مدخلاتك إلى سجل الفحوصات.</p><button className="button button-primary" type="button" onClick={() => window.location.reload()}><RefreshCw size={16} /> إعادة تحميل الصفحة</button></main>;
    }
    return this.props.children;
  }
}
