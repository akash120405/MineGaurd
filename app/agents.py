"""AutoGen message-driven collaboration: coordinator -> analyst -> monitor -> escalation."""
import json
import time
from dataclasses import dataclass
from autogen_core import AgentId, MessageContext, RoutedAgent, SingleThreadedAgentRuntime, message_handler
from . import db, tools, providers

@dataclass
class Task:
    job_id: str
    evidence_id: str

@dataclass
class Package:
    job_id: str
    evidence: dict
    rules: list
    analysis: dict

@dataclass
class Report:
    job_id: str
    data: dict

def trace(job,agent,tool,start,detail):
    db.execute('INSERT INTO traces(job_id,agent,tool,duration_ms,detail,created) VALUES(?,?,?,?,?,?)',(job,agent,tool,round((time.perf_counter()-start)*1000,2),json.dumps(detail),time.time()))

class EvidenceAnalyst(RoutedAgent):
    def __init__(self):
        super().__init__('Retrieve evidence and relevant policies; produce source-grounded analysis')

    @message_handler
    async def handle(self,message:Task,ctx:MessageContext)->Report:
        start=time.perf_counter()
        evidence=tools.get_evidence(message.evidence_id)
        # Tool plan is constrained by the inspection schema, never untrusted prose.
        rules=tools.search_rules('methane airflow ventilation dust '+evidence['notes'],100)
        flagged=bool(tools.INJECTION.search(evidence['notes']))
        evidence_text=json.dumps(evidence,ensure_ascii=False)
        if flagged:
            raw,provider,errors={'claims':[]},'blocked',['Possible prompt injection: AI processing blocked; human review required']
        else:
            raw,provider,errors=await providers.analyze(json.dumps({'evidence':evidence,'rules':rules},ensure_ascii=False))
        analysis=tools.validate_claims(raw,rules,evidence_text)
        analysis.update(provider=provider,errors=errors,injection_flag=flagged)
        trace(message.job_id,'Evidence Analyst','get_evidence + search_rules + provider',start,{'provider':provider,'retrieved':len(rules),'rejected':len(analysis['rejected']),'errors':errors})
        return await self.send_message(Package(message.job_id,evidence,rules,analysis),AgentId('monitor','default'))

class ComplianceMonitor(RoutedAgent):
    def __init__(self):
        super().__init__('Evaluate structured observations against versioned policies')

    @message_handler
    async def handle(self,message:Package,ctx:MessageContext)->Report:
        start=time.perf_counter()
        findings=tools.evaluate(message.evidence,message.rules)
        data={'evidence':message.evidence,'findings':findings,'analysis':message.analysis,'plan':['Retrieve inspection and applicable policy corpus','Validate evidence and screen untrusted instructions','Delegate grounded analysis to provider','Evaluate each structured threshold','Validate citations and request human review'],'requires_review':any(f['status']!='pass' for f in findings) or message.analysis['injection_flag'] or not findings}
        trace(message.job_id,'Compliance Monitor','evaluate_policy',start,{'checks':len(findings),'requires_review':data['requires_review']})
        return await self.send_message(Report(message.job_id,data),AgentId('escalation','default'))

class EscalationAgent(RoutedAgent):
    def __init__(self):
        super().__init__('Prepare escalation for human approval, never execute operational changes')

    @message_handler
    async def handle(self,message:Report,ctx:MessageContext)->Report:
        start=time.perf_counter()
        data=message.data
        data['priority']='high' if any(f['status']=='breach' for f in data['findings']) else 'medium' if data['requires_review'] else 'low'
        data['recommendation']='Review the cited evidence and assign a qualified safety officer. No external notification or mine operation is automated.' if data['requires_review'] else 'Recorded checks match the configured policy. This is not a mine safety clearance.'
        data['status']='awaiting_review' if data['requires_review'] else 'recorded'
        trace(message.job_id,'Escalation Agent','prepare_review',start,{'priority':data['priority'],'status':data['status']})
        return message

async def run_job(job):
    runtime=SingleThreadedAgentRuntime()
    await EvidenceAnalyst.register(runtime,'analyst',EvidenceAnalyst)
    await ComplianceMonitor.register(runtime,'monitor',ComplianceMonitor)
    await EscalationAgent.register(runtime,'escalation',EscalationAgent)
    runtime.start()
    try:
        report=await runtime.send_message(Task(job['id'],job['evidence_id']),AgentId('analyst','default'))
        db.execute('UPDATE jobs SET status=?,result=?,error=NULL WHERE id=?',(report.data['status'],json.dumps(report.data),job['id']))
        db.audit('agent-runtime','workflow.completed',{'job_id':job['id'],'status':report.data['status']})
    finally:
        await runtime.stop_when_idle()
