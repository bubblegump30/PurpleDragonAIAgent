"""Age is a review hint, never proof that information is correct or current."""
from datetime import datetime,timezone

def freshness(value,days=30):
    try:
        parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
        if parsed.tzinfo is None:raise ValueError('timezone missing')
        elapsed=(datetime.now(timezone.utc)-parsed).total_seconds()
        if elapsed < -86400:return {'status':'future','age_days':None,'review_needed':True,'warning':'Timestamp is in the future; review this reference.'}
        age=max(0,int(elapsed//86400))
        return {'status':'aged' if age>=days else 'recent','age_days':age,'review_needed':age>=days,
                'warning':f'Reference is at least {days} days old; review before relying on it.' if age>=days else 'Recent timestamp does not verify accuracy or publication date.'}
    except (AttributeError,TypeError,ValueError,OverflowError):
        return {'status':'unknown','age_days':None,'review_needed':True,'warning':'Reference age is unknown; review its date and evidence.'}
